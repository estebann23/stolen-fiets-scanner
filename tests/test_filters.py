"""SPEC 7.2 stage 1: serial bypass, posted-after-theft, e-bike, 25 km radius."""

from __future__ import annotations

from config import MATCH_RADIUS_KM
from matching.filters import apply_filters, haversine_km

MAASTRICHT = (50.8483, 5.6886)
HEERLEN = (50.8870, 5.9795)
AMSTERDAM = (52.3676, 4.9041)


def listing(listing_id: str, **overrides) -> dict:
    row = {
        "id": listing_id,
        "posted_at": None,
        "lat": None,
        "lon": None,
        "is_electric": None,
        "serial_found": None,
        "attributes": {},
    }
    row.update(overrides)
    return row


def report(**overrides) -> dict:
    row = {
        "stolen_at": "2026-06-01T00:00:00",
        "stolen_lat": MAASTRICHT[0],
        "stolen_lon": MAASTRICHT[1],
        "serial": None,
        "is_electric": None,
    }
    row.update(overrides)
    return row


def test_haversine_known_distance():
    km = haversine_km(*MAASTRICHT, *HEERLEN)
    assert 20.0 < km < 24.0
    assert haversine_km(*MAASTRICHT, *AMSTERDAM) > 150.0


def test_haversine_zero_for_same_point():
    assert haversine_km(*MAASTRICHT, *MAASTRICHT) == 0.0


def test_posted_before_theft_is_dropped():
    kept, hits = apply_filters(
        report(),
        [listing("a", posted_at="2026-05-01T00:00:00")],
        MATCH_RADIUS_KM,
    )
    assert kept == []
    assert hits == set()


def test_posted_after_theft_is_kept():
    kept, _ = apply_filters(
        report(),
        [listing("a", posted_at="2026-06-02T00:00:00")],
        MATCH_RADIUS_KM,
    )
    assert [row["id"] for row in kept] == ["a"]


def test_unparseable_posted_at_is_kept():
    # Marktplaats ships 'Vandaag'/'Gisteren' rather than ISO dates.
    kept, _ = apply_filters(
        report(),
        [listing("a", posted_at="Vandaag"), listing("b", posted_at="Gisteren")],
        MATCH_RADIUS_KM,
    )
    assert {row["id"] for row in kept} == {"a", "b"}


def test_missing_posted_at_is_kept():
    kept, _ = apply_filters(report(), [listing("a")], MATCH_RADIUS_KM)
    assert len(kept) == 1


def test_electric_disagreement_is_dropped():
    kept, _ = apply_filters(
        report(is_electric=True),
        [listing("a", is_electric=False)],
        MATCH_RADIUS_KM,
    )
    assert kept == []


def test_electric_agreement_is_kept():
    kept, _ = apply_filters(
        report(is_electric=True),
        [listing("a", is_electric=True)],
        MATCH_RADIUS_KM,
    )
    assert len(kept) == 1


def test_electric_unknown_on_either_side_is_kept():
    kept, _ = apply_filters(
        report(is_electric=None),
        [listing("a", is_electric=True), listing("b", is_electric=None)],
        MATCH_RADIUS_KM,
    )
    assert {row["id"] for row in kept} == {"a", "b"}


def test_distance_beyond_radius_is_dropped():
    kept, _ = apply_filters(
        report(),
        [listing("far", lat=AMSTERDAM[0], lon=AMSTERDAM[1])],
        MATCH_RADIUS_KM,
    )
    assert kept == []


def test_distance_within_radius_is_kept():
    kept, _ = apply_filters(
        report(),
        [listing("near", lat=HEERLEN[0], lon=HEERLEN[1])],
        MATCH_RADIUS_KM,
    )
    assert len(kept) == 1


def test_missing_coords_are_kept_conservatively():
    kept, _ = apply_filters(
        report(stolen_lat=None, stolen_lon=None),
        [listing("far", lat=AMSTERDAM[0], lon=AMSTERDAM[1])],
        MATCH_RADIUS_KM,
    )
    assert len(kept) == 1


def test_serial_hit_bypasses_every_other_filter():
    hit = listing(
        "serial",
        posted_at="2020-01-01T00:00:00",  # before theft
        lat=AMSTERDAM[0],
        lon=AMSTERDAM[1],  # far away
        is_electric=False,
        serial_found="GZ0123456",
    )
    kept, hits = apply_filters(
        report(serial="GZO123456", is_electric=True),
        [hit],
        MATCH_RADIUS_KM,
    )
    assert hits == {"serial"}
    assert [row["id"] for row in kept] == ["serial"]


def test_serial_found_read_from_nested_attributes():
    hit = listing("nested", attributes={"serial_found": "GZ0123456"})
    hit["serial_found"] = None
    _, hits = apply_filters(report(serial="GZ0123456"), [hit], MATCH_RADIUS_KM)
    assert hits == {"nested"}
