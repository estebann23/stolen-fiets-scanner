"""SPEC 7.2: short human reasons (serial, shared attrs, marks, verifier, time/distance)."""

from __future__ import annotations

from matching.explain import explain
from matching.verifier import Verdict

REPORT = {
    "stolen_at": "2026-09-01T00:00:00",
    "stolen_lat": 50.8483,
    "stolen_lon": 5.6886,
    "brand": "Gazelle",
    "color": "black",
    "attributes": {
        "brand": "Gazelle",
        "frame_shape": "low-step",
        "accessories": ["rear rack"],
        "marks": ["scratch on top tube"],
    },
}

LISTING = {
    "posted_at": "2026-09-04T00:00:00",
    "lat": 50.8870,
    "lon": 5.9795,
    "attributes": {
        "brand": "Gazelle",
        "colors": ["black"],
        "frame_shape": "low-step",
        "accessories": ["rear rack"],
        "marks": ["scratch on top tube"],
    },
}


def test_serial_match_is_the_first_reason():
    reasons = explain(REPORT, LISTING, {"image": 0.9}, None, serial_match=True)
    assert reasons[0] == "Exact serial match"


def test_shared_attributes_are_summarised():
    reasons = explain(REPORT, LISTING, {}, None)
    joined = " | ".join(reasons)
    assert "same brand (Gazelle)" in joined
    assert "same colour (black)" in joined
    assert "same low-step frame" in joined
    assert "same rear rack" in joined


def test_unknown_frame_shape_is_not_reported_as_a_match():
    report = {**REPORT, "attributes": {**REPORT["attributes"], "frame_shape": "unknown"}}
    listing = {**LISTING, "attributes": {**LISTING["attributes"], "frame_shape": "unknown"}}
    assert "unknown frame" not in " ".join(explain(report, listing, {}, None))


def test_shared_marks_are_listed():
    assert any("shared marks" in reason for reason in explain(REPORT, LISTING, {}, None))


def test_mark_component_without_exact_overlap_falls_back_to_a_generic_line():
    report = {**REPORT, "attributes": {**REPORT["attributes"], "marks": ["dent on fork"]}}
    reasons = explain(report, LISTING, {"marks": 0.3}, None)
    assert "overlapping distinctive marks" in reasons


def test_verifier_reasons_are_appended_without_duplicates():
    verdict = Verdict(verdict="likely_same", reasons=["same sticker", "same sticker"], confidence=0.9)
    reasons = explain(REPORT, LISTING, {}, verdict)
    assert reasons.count("same sticker") == 1


def test_time_and_distance_line():
    reasons = explain(REPORT, LISTING, {}, None)
    tail = [r for r in reasons if "km away" in r]
    assert tail
    assert "posted 3 days after theft" in tail[0]


def test_listing_posted_before_theft_omits_the_day_count():
    listing = {**LISTING, "posted_at": "2026-08-01T00:00:00"}
    joined = " ".join(explain(REPORT, listing, {}, None))
    assert "days after theft" not in joined


def test_strong_photo_similarity_is_the_last_resort_reason():
    bare_report = {"stolen_at": None, "attributes": {}}
    bare_listing = {"attributes": {}}
    assert explain(bare_report, bare_listing, {"image": 0.85}, None) == ["strong photo similarity"]
    assert explain(bare_report, bare_listing, {"image": 0.2}, None) == []


def test_reasons_are_capped_at_six():
    verdict = Verdict(verdict="likely_same", reasons=[f"r{i}" for i in range(20)], confidence=1.0)
    assert len(explain(REPORT, LISTING, {"marks": 1.0}, verdict, serial_match=True)) <= 6


def test_explain_tolerates_empty_inputs():
    assert explain({}, {}, {}, None) == []
