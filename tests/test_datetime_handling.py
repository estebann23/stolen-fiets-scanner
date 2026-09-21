"""Timestamp parsing across filters and explain (SPEC 7.2: unparseable dates must not drop)."""

from __future__ import annotations

from config import MATCH_RADIUS_KM
from matching.explain import explain
from matching.filters import apply_filters
from matching.filters import parse_timestamp as filters_parse_dt

REPORT = {"stolen_at": "2026-06-01T00:00:00", "stolen_lat": None, "stolen_lon": None, "serial": None}


def test_parse_dt_accepts_dates_and_datetimes():
    assert filters_parse_dt("2026-06-01") is not None
    assert filters_parse_dt("2026-06-01T12:30:00") is not None
    assert filters_parse_dt("2026-06-01T12:30:00Z") is not None


def test_parse_dt_rejects_marktplaats_relative_labels():
    assert filters_parse_dt("Vandaag") is None
    assert filters_parse_dt("Gisteren") is None
    assert filters_parse_dt("") is None
    assert filters_parse_dt(None) is None


def test_parse_dt_returns_naive_datetimes_for_every_offset():
    """Mixing naive and aware datetimes raises TypeError on comparison."""
    for raw in ("2026-06-01T12:00:00Z", "2026-06-01T12:00:00+02:00", "2026-06-01T12:00:00-05:00"):
        parsed = filters_parse_dt(raw)
        assert parsed is not None, raw
        assert parsed.tzinfo is None, f"{raw} parsed as timezone-aware: {parsed!r}"


def test_filters_survive_a_negative_utc_offset_on_a_listing():
    listing = {
        "id": "tz",
        "posted_at": "2026-07-01T12:00:00-05:00",
        "lat": None,
        "lon": None,
        "is_electric": None,
        "serial_found": None,
        "attributes": {},
    }
    kept, _ = apply_filters(REPORT, [listing], MATCH_RADIUS_KM)
    assert [row["id"] for row in kept] == ["tz"]


def test_explain_survives_a_negative_utc_offset_on_a_listing():
    reasons = explain(
        {"stolen_at": "2026-06-01T00:00:00", "attributes": {}},
        {"posted_at": "2026-07-01T12:00:00-05:00", "attributes": {}},
        {},
        None,
    )
    assert any("days after theft" in reason for reason in reasons)
