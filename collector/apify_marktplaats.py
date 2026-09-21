"""One-time Marktplaats scrape via Apify (`haketa/marktplaats-scraper`)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from apify_client import ApifyClient

from config import (
    APIFY_API_TOKEN,
    APIFY_DATASET_ID,
    APIFY_MARKTPLAATS_ACTOR_ID,
    ROOT,
)

# Maastricht centrum (Vrijthof / 6211). Used when the actor has no lat/lon.
MAASTRICHT = (50.851368, 5.690972)

CITY_COORDS: dict[str, tuple[float, float]] = {
    "maastricht": MAASTRICHT,
    "meerssen": (50.8856, 5.7553),
    "valkenburg": (50.8647, 5.8320),
    "heerlen": (50.8882, 5.9795),
    "sittard": (50.9980, 5.8694),
    "geleen": (50.9742, 5.8291),
    "eijsden": (50.7790, 5.7094),
    "margraten": (50.8225, 5.8206),
    "gulpen": (50.8147, 5.8911),
    "kerkrade": (50.8658, 6.0625),
    "landgraaf": (50.9064, 6.0281),
    "brunssum": (50.9467, 5.9708),
    "beek": (50.9394, 5.7972),
    "stein": (50.9692, 5.7661),
    "lanaken": (50.8931, 5.6497),
    "maasmechelen": (50.9636, 5.6947),
    "hasselt": (50.9307, 5.3378),
}

_ID_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


def apify_token() -> str:
    token = APIFY_API_TOKEN
    if not token:
        raise RuntimeError(
            "Missing Apify token. Set APIFY_KEY or APIFY_API_TOKEN in .env.local"
        )
    return token


def client() -> ApifyClient:
    return ApifyClient(apify_token())


def verify_connection() -> dict[str, Any]:
    """Confirm the token works without starting a paid actor run."""
    me = client().user().get()
    if hasattr(me, "model_dump"):
        data = me.model_dump()
    elif hasattr(me, "dict"):
        data = me.dict()
    else:
        data = dict(me)
    return {
        "id": data.get("id"),
        "username": data.get("username"),
    }


def build_run_input(queries: dict[str, Any]) -> dict[str, Any]:
    region = queries.get("region") or {}
    radius_km = float(region.get("radius_km") or 25)
    max_listings = int(queries.get("max_listings") or 300)
    max_listings = max(200, min(500, max_listings))
    payload: dict[str, Any] = {
        "platform": queries.get("platform") or "marktplaats.nl",
        "query": queries.get("query") or "fiets",
        "categoryId": str(queries.get("category_id") or "1655"),
        "postcode": str(region.get("postcode") or "6211"),
        "distanceMeters": int(radius_km * 1000),
        "sortBy": "SORT_INDEX",
        "sortOrder": "DECREASING",
        "scrapeDetails": True,
        "maxListings": max_listings,
        "requestDelay": 500,
    }
    bands = queries.get("price_bands") or {}
    min_eur = bands.get("min_eur")
    max_eur = bands.get("max_eur")
    if min_eur is not None:
        payload["minPrice"] = int(float(min_eur) * 100)
    if max_eur is not None:
        payload["maxPrice"] = int(float(max_eur) * 100)
    return payload


def run_scrape(queries: dict[str, Any], timeout_secs: int = 900) -> dict[str, Any]:
    run_input = build_run_input(queries)
    print(
        "Apify run:",
        APIFY_MARKTPLAATS_ACTOR_ID,
        run_input["query"],
        run_input["postcode"],
        f"{run_input['distanceMeters']}m",
        f"max={run_input['maxListings']}",
    )
    run = client().actor(APIFY_MARKTPLAATS_ACTOR_ID).call(
        run_input=run_input,
        run_timeout=timedelta(seconds=timeout_secs),
        wait_duration=timedelta(seconds=timeout_secs),
    )
    if run is None:
        raise RuntimeError("Apify actor call returned no run")
    if hasattr(run, "model_dump"):
        run_data = run.model_dump()
    else:
        run_data = dict(run)
    dataset_id = (
        run_data.get("default_dataset_id")
        or run_data.get("defaultDatasetId")
        or APIFY_DATASET_ID
    )
    if not dataset_id:
        raise RuntimeError("Apify run finished without a dataset id")
    items = list(client().dataset(dataset_id).iterate_items())
    meta = {
        "run_id": run_data.get("id"),
        "dataset_id": dataset_id,
        "status": str(run_data.get("status")),
        "item_count": len(items),
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": run_input,
    }
    meta_path = ROOT / "data" / "raw" / "apify_last_run.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"meta": meta, "items": items}


def _coords_for_city(city: str | None) -> tuple[float | None, float | None]:
    if not city:
        return MAASTRICHT
    key = city.lower().split(",")[0].strip()
    for name, pair in CITY_COORDS.items():
        if name.strip() in key or key in name.strip():
            return pair
    return MAASTRICHT


def _as_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "model_dump"):
        return raw.model_dump()
    if hasattr(raw, "dict"):
        return raw.dict()
    return dict(raw)


def _listing_id(raw: dict[str, Any]) -> str:
    raw_id = raw.get("listingId") or raw.get("id") or raw.get("itemId") or raw.get("url")
    text = _ID_SAFE.sub("_", str(raw_id or "unknown")).strip("_")
    if not text.startswith("m"):
        text = f"m_{text}"
    return text[:80]


def map_apify_item(raw: dict[str, Any]) -> dict[str, Any]:
    price = raw.get("price")
    if price is None and isinstance(raw.get("priceCents"), (int, float)):
        price = float(raw["priceCents"]) / 100.0
    elif isinstance(price, str):
        digits = re.sub(r"[^0-9.]", "", price.replace(",", "."))
        price = float(digits) if digits else None
    city = raw.get("location") or raw.get("city") or "Maastricht"
    if isinstance(city, dict):
        city = city.get("city") or city.get("name") or "Maastricht"
    lat, lon = _coords_for_city(str(city))
    images = raw.get("images") or raw.get("imageUrls") or []
    if isinstance(images, str):
        images = [images]
    if raw.get("imageUrl"):
        images = [raw["imageUrl"], *images]
    urls = [u for u in images if isinstance(u, str) and u.startswith("http")]
    seller = raw.get("sellerId")
    if seller is not None:
        seller = f"s_{seller}"
    return {
        "id": _listing_id(raw),
        "title": raw.get("title") or "",
        "description": raw.get("description") or raw.get("rawDescription") or "",
        "price": price,
        "location": str(city),
        "lat": lat,
        "lon": lon,
        "posted_at": raw.get("date") or raw.get("publishedAt") or raw.get("postedTimestamp"),
        "seller_id": seller,
        "url": raw.get("url"),
        "image_urls": urls[:5],
        "source": "apify",
        "platform": raw.get("platform") or "marktplaats.nl",
    }


def map_dataset(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in items:
        row = map_apify_item(_as_dict(raw))
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        mapped.append(row)
    return mapped


if __name__ == "__main__":
    info = verify_connection()
    print("Apify connected", info.get("username") or info.get("id"))
