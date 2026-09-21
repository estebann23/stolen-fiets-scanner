"""Hard filters: serial, posted-after-theft, distance, bike type."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from enrichment.serial_ocr import normalise_serial

_OCR_MAP = str.maketrans({"O": "0", "I": "1", "L": "1", "S": "5", "B": "8"})


def canonical_serial(s: str) -> str:
    """Normalise then map OCR confusables (O/0, I/L/1, S/5, B/8)."""
    return normalise_serial(s).translate(_OCR_MAP)


def serial_matches(report_serial: str | None, listing_serial: str | None) -> bool:
    if not report_serial or not listing_serial:
        return False
    return canonical_serial(report_serial) == canonical_serial(listing_serial)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    d_phi = math.radians(float(lat2) - float(lat1))
    d_lambda = math.radians(float(lon2) - float(lon1))
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(min(1.0, math.sqrt(a)))


def parse_timestamp(raw: Any) -> datetime | None:
    """ISO date/datetime → UTC-naive datetime, matching how reports are stored.

    Returns None for Marktplaats relative labels ("Vandaag"), which callers
    must treat as unknown rather than as a mismatch.
    """
    if raw is None or raw == "":
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _as_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    return None


def apply_filters(
    report: dict[str, Any],
    listings: list[dict[str, Any]],
    radius_km: float,
) -> tuple[list[dict[str, Any]], set[str]]:
    serial_hit_ids: set[str] = set()
    report_serial = report.get("serial")
    for listing in listings:
        listing_serial = listing.get("serial_found")
        if listing_serial is None:
            attrs = listing.get("attributes") or {}
            listing_serial = attrs.get("serial_found")
        if serial_matches(report_serial, listing_serial):
            serial_hit_ids.add(str(listing["id"]))

    stolen_at = parse_timestamp(report.get("stolen_at"))
    report_lat = report.get("stolen_lat")
    report_lon = report.get("stolen_lon")
    report_electric = _as_bool(report.get("is_electric"))

    kept: list[dict[str, Any]] = []
    for listing in listings:
        listing_id = str(listing["id"])
        if listing_id in serial_hit_ids:
            kept.append(listing)
            continue

        posted_at = parse_timestamp(listing.get("posted_at"))
        if stolen_at is not None and posted_at is not None and posted_at < stolen_at:
            continue

        listing_electric = _as_bool(listing.get("is_electric"))
        if (
            report_electric is not None
            and listing_electric is not None
            and report_electric != listing_electric
        ):
            continue

        listing_lat = listing.get("lat")
        listing_lon = listing.get("lon")
        if (
            report_lat is not None
            and report_lon is not None
            and listing_lat is not None
            and listing_lon is not None
        ):
            distance = haversine_km(
                float(report_lat),
                float(report_lon),
                float(listing_lat),
                float(listing_lon),
            )
            if distance > float(radius_km):
                continue

        kept.append(listing)

    return kept, serial_hit_ids


def main() -> None:
    print(canonical_serial("GZ1234S6"))
    print(serial_matches("GZO123", "GZ0123"))


if __name__ == "__main__":
    main()
