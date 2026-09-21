"""SPEC 5.2: suspicion_score = 0.5 price + 0.35 phrases + 0.15 seller proxy."""

from __future__ import annotations

import pytest

from config import RISK_WEIGHTS
from enrichment.risk_signals import (
    SUSPICION_PHRASES,
    build_price_medians,
    compute_suspicion,
    enrich_all_risk,
)

MEDIANS = {"city": 800.0, "global": 800.0, None: 800.0}


def test_spec_risk_weights_are_unchanged():
    assert RISK_WEIGHTS == {"price": 0.5, "phrases": 0.35, "seller": 0.15}


def test_clean_listing_scores_zero():
    score, reasons = compute_suspicion(
        {"title": "Gazelle Orange C7", "description": "Nette stadsfiets met bon.", "price": 900.0},
        "city",
        MEDIANS,
        12,
    )
    assert score == 0.0
    assert reasons == []


def test_price_component_scales_with_the_discount():
    # half the median -> price_score 0.5 -> 0.5 * 0.5 = 0.25
    score, reasons = compute_suspicion(
        {"title": "Gazelle", "description": "", "price": 400.0}, "city", MEDIANS, 12
    )
    assert score == pytest.approx(0.25)
    assert "price well below type/global median" in reasons


def test_price_at_or_above_median_contributes_nothing():
    score, _ = compute_suspicion(
        {"title": "x", "description": "", "price": 800.0}, "city", MEDIANS, 12
    )
    assert score == 0.0


def test_phrase_component_is_a_fraction_of_all_phrases():
    score, reasons = compute_suspicion(
        {"title": "", "description": "Snel weg, geen bon.", "price": 900.0}, "city", MEDIANS, 12
    )
    assert score == pytest.approx(0.35 * 2 / len(SUSPICION_PHRASES))
    assert "phrase: snel weg" in reasons
    assert "phrase: geen bon" in reasons


def test_all_phrases_present_gives_the_full_phrase_weight():
    blob = " ".join(SUSPICION_PHRASES)
    score, _ = compute_suspicion(
        {"title": "", "description": blob, "price": 900.0}, "city", MEDIANS, 12
    )
    assert score == pytest.approx(0.35)


def test_phrase_matching_is_case_insensitive():
    score, _ = compute_suspicion(
        {"title": "MOET WEG", "description": "", "price": 900.0}, "city", MEDIANS, 12
    )
    assert score > 0


def test_single_listing_seller_adds_the_proxy_weight():
    score, reasons = compute_suspicion(
        {"title": "", "description": "", "price": 900.0}, "city", MEDIANS, 1
    )
    assert score == pytest.approx(0.15)
    assert "single-listing seller (activity proxy)" in reasons


def test_worst_case_is_clamped_to_one():
    blob = " ".join(SUSPICION_PHRASES)
    score, _ = compute_suspicion(
        {"title": "", "description": blob, "price": 0.01}, "city", MEDIANS, 1
    )
    assert score == pytest.approx(0.5 + 0.35 + 0.15, abs=1e-3)
    assert score <= 1.0


def test_unknown_bike_type_falls_back_to_the_global_median():
    score, _ = compute_suspicion(
        {"title": "", "description": "", "price": 400.0}, "unseen-type", MEDIANS, 12
    )
    assert score == pytest.approx(0.25)


def test_missing_price_contributes_nothing():
    score, _ = compute_suspicion({"title": "", "description": ""}, "city", MEDIANS, 12)
    assert score == 0.0


def test_build_price_medians_groups_by_bike_type(conn):
    rows = [
        ("l1", 100.0, "city"),
        ("l2", 300.0, "city"),
        ("l3", 2000.0, "e-bike"),
    ]
    for listing_id, price, bike_type in rows:
        conn.execute("INSERT INTO listings (id, price) VALUES (?, ?)", (listing_id, price))
        conn.execute(
            "INSERT INTO listing_attributes (listing_id, bike_type) VALUES (?, ?)",
            (listing_id, bike_type),
        )
    conn.commit()
    medians = build_price_medians(conn)
    assert medians["city"] == pytest.approx(200.0)
    assert medians["e-bike"] == pytest.approx(2000.0)
    assert medians["global"] == pytest.approx(300.0)


def test_enrich_all_risk_overwrites_every_listing(conn):
    conn.execute(
        "INSERT INTO listings (id, title, description, price, seller_id, suspicion_score)"
        " VALUES ('l1', 'Gazelle', 'Snel weg', 100.0, 's1', 0.99)"
    )
    conn.execute(
        "INSERT INTO listings (id, title, description, price, seller_id, suspicion_score)"
        " VALUES ('l2', 'Batavus', 'Nette fiets', 900.0, 's2', NULL)"
    )
    conn.commit()
    assert enrich_all_risk(conn) == 2
    scores = dict(conn.execute("SELECT id, suspicion_score FROM listings").fetchall())
    assert scores["l1"] > scores["l2"]
    assert all(0.0 <= value <= 1.0 for value in scores.values())


def test_enrich_all_risk_is_deterministic(conn):
    conn.execute(
        "INSERT INTO listings (id, title, description, price, seller_id)"
        " VALUES ('l1', 'Gazelle', 'Snel weg', 100.0, 's1')"
    )
    conn.commit()
    enrich_all_risk(conn)
    first = conn.execute("SELECT suspicion_score FROM listings WHERE id='l1'").fetchone()[0]
    enrich_all_risk(conn)
    second = conn.execute("SELECT suspicion_score FROM listings WHERE id='l1'").fetchone()[0]
    assert first == second
