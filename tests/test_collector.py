"""SPEC 5.1: Apify mapping, dedupe, queries.yaml plan, and offline demo corpus."""

from __future__ import annotations

import random

import pytest

from collector.apify_marktplaats import build_run_input, map_apify_item, map_dataset
from collector.collect import load_queries
from collector.demo_corpus import build_demo_listings
from matching.filters import parse_timestamp as _parse_dt


def test_queries_yaml_matches_the_spec_plan():
    queries = load_queries()
    assert queries["query"] == "fiets"
    assert str(queries["category_id"]) == "1655"
    assert str(queries["region"]["postcode"]) == "6211"
    assert float(queries["region"]["radius_km"]) == 25.0
    assert int(queries["max_listings"]) == 300


def test_queries_yaml_has_no_price_cap():
    """SPEC 5.1: a listing-count cap replaced the old EUR 200-500 band."""
    bands = load_queries().get("price_bands") or {}
    assert not bands.get("min_eur") and not bands.get("max_eur")


def test_build_run_input_translates_the_plan_to_actor_arguments():
    payload = build_run_input(load_queries())
    assert payload["query"] == "fiets"
    assert payload["categoryId"] == "1655"
    assert payload["postcode"] == "6211"
    assert payload["distanceMeters"] == 25000
    assert payload["maxListings"] == 300


def test_map_apify_item_normalises_price_strings():
    row = map_apify_item({"listingId": "m123", "title": "Fiets", "price": "EUR 249,50"})
    assert row["price"] == pytest.approx(249.50)


def test_map_apify_item_converts_price_cents():
    row = map_apify_item({"listingId": "m123", "priceCents": 24950})
    assert row["price"] == pytest.approx(249.50)


def test_map_apify_item_keeps_only_http_image_urls():
    row = map_apify_item(
        {
            "listingId": "m1",
            "imageUrl": "https://cdn.example/1.jpg",
            "images": ["https://cdn.example/2.jpg", "//broken", None],
        }
    )
    assert row["image_urls"] == ["https://cdn.example/1.jpg", "https://cdn.example/2.jpg"]


def test_map_dataset_dedupes_by_listing_id():
    items = [{"listingId": "m1"}, {"listingId": "m1"}, {"listingId": "m2"}]
    assert [row["id"] for row in map_dataset(items)] == ["m1", "m2"]


def test_mapped_posted_at_is_passed_through_verbatim():
    """Marktplaats ships relative labels; the matcher must treat them as unparseable."""
    row = map_apify_item({"listingId": "m1", "date": "Vandaag"})
    assert row["posted_at"] == "Vandaag"
    assert _parse_dt(row["posted_at"]) is None


def test_demo_corpus_is_deterministic_for_a_seed():
    queries = load_queries()
    args = dict(brands=list(queries["brands"]), types=list(queries["types"]), n_keep=20, n_junk=5)
    first = build_demo_listings(rng=random.Random(42), **args)
    second = build_demo_listings(rng=random.Random(42), **args)
    assert [row["id"] for row in first] == [row["id"] for row in second]


def test_demo_corpus_rows_carry_iso_dates_and_coordinates():
    queries = load_queries()
    rows = build_demo_listings(
        brands=list(queries["brands"]),
        types=list(queries["types"]),
        rng=random.Random(7),
        n_keep=20,
        n_junk=0,
    )
    assert len(rows) == 20
    for row in rows:
        assert _parse_dt(row["posted_at"]) is not None
        assert row["lat"] is not None and row["lon"] is not None
        assert row["url"].startswith("https://")
