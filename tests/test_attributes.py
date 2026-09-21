"""SPEC 5.2: strict-JSON BikeAttributes, null fallback, idempotent listing enrichment."""

from __future__ import annotations

import json

import pytest

import enrichment.attributes as attrs_mod
from enrichment.attributes import BikeAttributes, enrich_listing, extract_attributes, store_attributes


def test_enum_coercion_keeps_allowed_values():
    assert BikeAttributes(bike_type="City").bike_type == "city"
    assert BikeAttributes(frame_shape="Low-Step").frame_shape == "low-step"


def test_out_of_vocabulary_enums_degrade_safely():
    assert BikeAttributes(bike_type="tandem").bike_type is None
    assert BikeAttributes(frame_shape="banana").frame_shape == "unknown"


def test_scalar_lists_are_coerced():
    assert BikeAttributes(colors="black").colors == ["black"]
    assert BikeAttributes(accessories=None).accessories is None
    assert BikeAttributes(marks=["a", 1]).marks == ["a", "1"]


def test_confidence_is_clamped_or_none():
    assert BikeAttributes(confidence=2).confidence == 1.0
    assert BikeAttributes(confidence=-1).confidence == 0.0
    assert BikeAttributes(confidence="n/a").confidence is None


def test_extract_attributes_returns_nulls_when_the_vlm_gives_nothing(monkeypatch):
    monkeypatch.setattr(attrs_mod, "call_vlm_json", lambda *a, **k: None)
    result = extract_attributes([], "een nette stadsfiets")
    assert result.brand is None
    assert result.confidence == 0.0


def test_extract_attributes_returns_nulls_on_schema_violation(monkeypatch):
    monkeypatch.setattr(attrs_mod, "call_vlm_json", lambda *a, **k: {"colors": {"bad": "shape"}})
    result = extract_attributes([], "")
    assert result.colors is None


def test_extract_attributes_parses_a_good_payload(monkeypatch):
    payload = {
        "brand": "Gazelle",
        "model": "Orange C7",
        "bike_type": "city",
        "colors": ["black"],
        "frame_shape": "low-step",
        "wheel_size": "28",
        "is_electric": False,
        "accessories": ["rear rack"],
        "marks": ["scratch on top tube"],
        "confidence": 0.8,
    }
    monkeypatch.setattr(attrs_mod, "call_vlm_json", lambda *a, **k: payload)
    result = extract_attributes([], "")
    assert result.brand == "Gazelle"
    assert result.is_electric is False
    assert result.confidence == pytest.approx(0.8)


def test_store_attributes_writes_lists_as_json(conn):
    conn.execute("INSERT INTO listings (id) VALUES ('l1')")
    conn.commit()
    store_attributes(conn, "l1", BikeAttributes(brand="Gazelle", colors=["black", "grey"]))
    row = conn.execute("SELECT colors FROM listing_attributes WHERE listing_id='l1'").fetchone()
    assert json.loads(row["colors"]) == ["black", "grey"]


def test_store_attributes_never_clobbers_serial_found(conn):
    conn.execute("INSERT INTO listings (id) VALUES ('l1')")
    conn.execute(
        "INSERT INTO listing_attributes (listing_id, serial_found) VALUES ('l1', 'GZ123456')"
    )
    conn.commit()
    store_attributes(conn, "l1", BikeAttributes(brand="Gazelle"))
    row = conn.execute("SELECT brand, serial_found FROM listing_attributes WHERE listing_id='l1'").fetchone()
    assert row["brand"] == "Gazelle"
    assert row["serial_found"] == "GZ123456"


def test_enrich_listing_skips_when_a_brand_is_already_stored(conn, monkeypatch):
    monkeypatch.setattr(
        attrs_mod,
        "extract_attributes",
        lambda *a, **k: pytest.fail("must skip an already-enriched listing"),
    )
    conn.execute("INSERT INTO listings (id, description) VALUES ('l1', 'x')")
    conn.execute("INSERT INTO listing_attributes (listing_id, brand) VALUES ('l1', 'Gazelle')")
    conn.commit()
    assert enrich_listing(conn, "l1").brand == "Gazelle"


def test_enrich_listing_force_recomputes(conn, monkeypatch):
    calls = []
    monkeypatch.setattr(
        attrs_mod,
        "extract_attributes",
        lambda paths, desc: (calls.append(desc), BikeAttributes(brand="Batavus"))[1],
    )
    conn.execute("INSERT INTO listings (id, description) VALUES ('l1', 'nette fiets')")
    conn.execute("INSERT INTO listing_attributes (listing_id, brand) VALUES ('l1', 'Gazelle')")
    conn.commit()
    assert enrich_listing(conn, "l1", force=True).brand == "Batavus"
    assert calls == ["nette fiets"]


def test_enrich_listing_raises_for_an_unknown_listing(conn):
    with pytest.raises(ValueError):
        enrich_listing(conn, "does-not-exist")
