"""Price anomaly + suspicious phrasing → suspicion_score (not used in match score).

suspicion_score is displayed SEPARATELY and is never part of the match score
(SPEC hard rule).
"""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from statistics import median
from typing import Any

from config import RISK_WEIGHTS
from db import connect

log = logging.getLogger(__name__)

# Case-insensitive substring match on title + description (SPEC §5.2).
SUSPICION_PHRASES: tuple[str, ...] = (
    "zonder papieren",
    "geen bon",
    "geen sleutel",
    "snel weg",
    "moet weg",
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def build_price_medians(conn: sqlite3.Connection) -> dict[str | None, float]:
    """Median listing price by bike_type, plus a global median."""
    rows = conn.execute(
        """
        SELECT a.bike_type AS bike_type, l.price AS price
        FROM listings l
        LEFT JOIN listing_attributes a ON a.listing_id = l.id
        WHERE l.price IS NOT NULL
        """
    ).fetchall()
    grouped: dict[str | None, list[float]] = defaultdict(list)
    all_prices: list[float] = []
    for row in rows:
        price = row["price"]
        if price is None:
            continue
        value = float(price)
        all_prices.append(value)
        grouped[row["bike_type"]].append(value)

    medians: dict[str | None, float] = {}
    if all_prices:
        global_median = float(median(all_prices))
        medians["global"] = global_median
        medians[None] = global_median
    for bike_type, prices in grouped.items():
        if prices:
            medians[bike_type] = float(median(prices))
    return medians


def compute_suspicion(
    listing: dict[str, Any],
    bike_type: str | None,
    medians: dict[str | None, float],
    seller_listing_count: int,
) -> tuple[float, list[str]]:
    """Weighted [0,1] score + display reasons (never used in matching)."""
    reasons: list[str] = []

    price_raw = listing.get("price")
    group_median = medians.get(bike_type)
    if group_median is None:
        group_median = medians.get("global")
    if (
        price_raw is None
        or group_median is None
        or float(group_median) <= 0
        or float(price_raw) >= float(group_median)
    ):
        price_score = 0.0
    else:
        price_score = _clamp01(1.0 - float(price_raw) / float(group_median))
        if price_score > 0:
            reasons.append("price well below type/global median")

    blob = f"{listing.get('title') or ''} {listing.get('description') or ''}".lower()
    hits = [phrase for phrase in SUSPICION_PHRASES if phrase in blob]
    phrase_score = (len(hits) / len(SUSPICION_PHRASES)) if SUSPICION_PHRASES else 0.0
    for phrase in hits:
        reasons.append(f"phrase: {phrase}")

    # Proxy only: the scrape has no real seller history, just listing counts.
    if seller_listing_count <= 1:
        seller_score = 1.0
        reasons.append("single-listing seller (activity proxy)")
    else:
        seller_score = 0.0

    weights = RISK_WEIGHTS
    score = _clamp01(
        float(weights.get("price", 0.5)) * price_score
        + float(weights.get("phrases", 0.35)) * phrase_score
        + float(weights.get("seller", 0.15)) * seller_score
    )
    return score, reasons


def enrich_all_risk(conn: sqlite3.Connection) -> int:
    """Recompute listings.suspicion_score for every listing. Cheap and deterministic."""
    medians = build_price_medians(conn)
    seller_counts = {
        row["seller_id"]: int(row["n"])
        for row in conn.execute(
            "SELECT seller_id, COUNT(*) AS n FROM listings GROUP BY seller_id"
        )
    }
    bike_types = {
        row["listing_id"]: row["bike_type"]
        for row in conn.execute("SELECT listing_id, bike_type FROM listing_attributes")
    }
    updated = 0
    for row in conn.execute("SELECT * FROM listings"):
        listing = dict(row)
        listing_id = listing["id"]
        score, _reasons = compute_suspicion(
            listing,
            bike_types.get(listing_id),
            medians,
            seller_counts.get(listing.get("seller_id"), 1),
        )
        conn.execute(
            "UPDATE listings SET suspicion_score = ? WHERE id = ?",
            (score, listing_id),
        )
        updated += 1
    conn.commit()
    log.info("risk updated %s listings", updated)
    return updated


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    medians: dict[str | None, float] = {"city": 800.0, "global": 800.0, None: 800.0}
    low, _ = compute_suspicion(
        {
            "title": "Gazelle Orange C7",
            "description": "Nette stadsfiets met rek.",
            "price": 750.0,
        },
        "city",
        medians,
        12,
    )
    high, reasons = compute_suspicion(
        {
            "title": "Gazelle",
            "description": "Snel weg, geen bon.",
            "price": 80.0,
        },
        "city",
        medians,
        1,
    )
    print(f"normal={low:.3f} suspicious={high:.3f} reasons={reasons}")
    conn = connect()
    try:
        n = enrich_all_risk(conn)
        print(f"updated {n} listings")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
