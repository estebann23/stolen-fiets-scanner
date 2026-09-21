"""SPEC 5.1: drop parts, locks, accessories, kids' bikes, and wanted ads."""

from __future__ import annotations

import pytest

from collector.relevance_filter import filter_listings, is_relevant


@pytest.mark.parametrize(
    "title,description",
    [
        ("Gazelle Orange C7 damesfiets", "Nette stadsfiets met rek."),
        ("Batavus Mambo stadsfiets", "Kleur zwart, 28 inch."),
        ("VanMoof S3 e-bike", "Elektrische fiets, met bon."),
    ],
)
def test_real_bikes_are_kept(title, description):
    assert is_relevant({"title": title, "description": description}) is True


@pytest.mark.parametrize(
    "title,description",
    [
        ("Gezocht: Gazelle Orange dames", "Wil kopen stadsfiets."),
        ("AXA Defender kettingslot nieuw", "Fietsslot met 2 sleutels."),
        ("Kinderfiets 16 inch meisjes", "Roze kinderfiets."),
        ("Voorwiel 28 inch met band", "Los voorwiel, geen fiets."),
        ("Fietstassen set dubbel", "Accessoires voor bakfiets."),
        ("Batavus onderdelen partij", "Voorvork en zadel."),
        ("Loopfiets hout 2 jaar", "Peuter loopfiets."),
        ("Helm ABUS maat M", "Fietshelm, geen fiets."),
        ("Gevraagd VanMoof S3", "Zoek elektrische fiets."),
        ("Binnenband 28 inch 4 stuks", "Onderdelen."),
    ],
)
def test_junk_is_dropped(title, description):
    assert is_relevant({"title": title, "description": description}) is False


def test_wanted_ads_are_dropped_from_the_description_too():
    assert is_relevant({"title": "Gazelle Orange", "description": "Ik zoek deze fiets."}) is False


def test_kids_wheel_sizes_are_dropped_from_the_description():
    assert is_relevant({"title": "Fiets", "description": "Wielmaat 16 inch."}) is False
    assert is_relevant({"title": "Fiets", "description": "Wielmaat 28 inch."}) is True


def test_filter_listings_preserves_order():
    rows = [
        {"id": "a", "title": "Gazelle stadsfiets", "description": ""},
        {"id": "b", "title": "Kettingslot", "description": ""},
        {"id": "c", "title": "Batavus e-bike", "description": ""},
    ]
    assert [row["id"] for row in filter_listings(rows)] == ["a", "c"]


def test_missing_fields_do_not_crash():
    assert is_relevant({}) is True
