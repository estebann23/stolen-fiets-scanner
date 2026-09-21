"""Turn attributes + verdict into short human-readable match reasons."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from matching.filters import haversine_km
from matching.verifier import Verdict


def _parse_dt(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    try:
        return datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00").split("+")[0])
    except ValueError:
        return None


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def explain(
    report: dict[str, Any],
    listing: dict[str, Any],
    components: dict[str, Any],
    verdict: Verdict | None,
    *,
    serial_match: bool = False,
) -> list[str]:
    reasons: list[str] = []
    if serial_match:
        reasons.append("Exact serial match")

    attrs = listing.get("attributes") or {}
    report_attrs = report.get("attributes") or {}
    shared: list[str] = []
    brand_r = _norm(report_attrs.get("brand") or report.get("brand"))
    brand_l = _norm(attrs.get("brand"))
    if brand_r and brand_l and brand_r.lower() == brand_l.lower():
        shared.append(f"same brand ({brand_l})")
    color_r = _norm(report.get("color"))
    listing_colors = attrs.get("colors") or []
    if color_r and any(str(c).lower() == color_r.lower() for c in listing_colors):
        shared.append(f"same colour ({color_r})")
    frame_r = _norm(report_attrs.get("frame_shape"))
    frame_l = _norm(attrs.get("frame_shape"))
    if frame_r and frame_l and frame_r.lower() == frame_l.lower() and frame_l != "unknown":
        shared.append(f"same {frame_l} frame")
    acc_r = {str(x).lower() for x in (report_attrs.get("accessories") or [])}
    acc_l = {str(x).lower() for x in (attrs.get("accessories") or [])}
    acc_overlap = sorted(acc_r & acc_l)
    if acc_overlap:
        shared.append("same " + " and ".join(acc_overlap[:3]))
    if shared:
        reasons.append(" · ".join(shared))

    marks_r = {str(x).lower() for x in (report_attrs.get("marks") or []) if x}
    marks_l = {str(x).lower() for x in (attrs.get("marks") or []) if x}
    mark_hits = sorted(marks_r & marks_l)
    if mark_hits:
        reasons.append("shared marks: " + ", ".join(mark_hits[:2]))
    elif float(components.get("marks") or 0) > 0:
        reasons.append("overlapping distinctive marks")

    if verdict is not None:
        for item in verdict.reasons:
            if item and item not in reasons:
                reasons.append(str(item))

    stolen_at = _parse_dt(report.get("stolen_at"))
    posted_at = _parse_dt(listing.get("posted_at"))
    geo_bits: list[str] = []
    if stolen_at is not None and posted_at is not None:
        delta_days = (posted_at - stolen_at).days
        if delta_days >= 0:
            geo_bits.append(f"posted {delta_days} days after theft")
    lat1, lon1 = report.get("stolen_lat"), report.get("stolen_lon")
    lat2, lon2 = listing.get("lat"), listing.get("lon")
    if None not in (lat1, lon1, lat2, lon2):
        km = haversine_km(float(lat1), float(lon1), float(lat2), float(lon2))
        geo_bits.append(f"{km:.0f} km away")
    if geo_bits:
        reasons.append(", ".join(geo_bits))

    if not reasons and float(components.get("image") or 0) >= 0.7:
        reasons.append("strong photo similarity")
    return reasons[:6]


def main() -> None:
    print(
        explain(
            {"serial": "GZ1", "stolen_at": "2026-09-01", "stolen_lat": 50.85, "stolen_lon": 5.69},
            {
                "posted_at": "2026-09-04",
                "lat": 50.85,
                "lon": 5.70,
                "attributes": {"brand": "Gazelle", "colors": ["black"]},
            },
            {"image": 0.9, "marks": 0.0},
            None,
            serial_match=True,
        )
    )


if __name__ == "__main__":
    main()
