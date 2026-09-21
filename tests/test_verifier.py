"""SPEC 7.2 stage 3: VLM rerank over VERIFY_TOP_K, serial short-circuit, sort order."""

from __future__ import annotations

import pytest

from config import VERIFY_TOP_K
from matching.verifier import Verdict, rerank


def item(listing_id: str, score: float, serial_match: bool = False) -> dict:
    return {
        "listing_id": listing_id,
        "score": score,
        "serial_match": serial_match,
        "listing": {"id": listing_id, "image_paths": []},
    }


@pytest.fixture
def report():
    return {"id": "r_test", "images": []}


def test_verify_top_k_is_ten():
    assert VERIFY_TOP_K == 10


def test_only_top_k_candidates_are_sent_to_the_vlm(monkeypatch, report):
    seen: list[str] = []

    def fake_verify(report_paths, listing_paths):
        seen.append("call")
        return Verdict(verdict="possibly_same", reasons=[], confidence=0.5)

    monkeypatch.setattr("matching.verifier.verify_pair", fake_verify)
    scored = [item(f"L{i:02d}", 1.0 - i / 100) for i in range(25)]
    ranked = rerank(report, scored, 10)
    assert len(seen) == 10
    verified = [row for row in ranked if row["verdict"] is not None]
    assert {row["listing_id"] for row in verified} == {f"L{i:02d}" for i in range(10)}


def test_unverified_candidates_get_a_null_verdict(monkeypatch, report):
    monkeypatch.setattr("matching.verifier.verify_pair", lambda a, b: None)
    ranked = rerank(report, [item("L1", 0.5)], 10)
    assert ranked[0]["verdict"] is None
    assert ranked[0]["verdict_obj"] is None


def test_serial_hits_skip_the_vlm_and_get_confidence_one(monkeypatch, report):
    monkeypatch.setattr(
        "matching.verifier.verify_pair",
        lambda a, b: pytest.fail("serial hits must not call the VLM"),
    )
    ranked = rerank(report, [item("S1", 1.0, serial_match=True)], 10)
    assert ranked[0]["verdict"] == "likely_same"
    assert ranked[0]["verdict_obj"].confidence == 1.0
    assert ranked[0]["verdict_obj"].reasons == ["exact serial match"]


def test_sort_order_is_verdict_then_score(monkeypatch, report):
    verdicts = {
        "a": "different",
        "b": "possibly_same",
        "c": "likely_same",
        "d": None,
    }

    def fake_verify(report_paths, listing_paths):
        return fake_verify.queue.pop(0)

    scored = [item(key, score) for key, score in [("a", 0.9), ("b", 0.8), ("c", 0.7), ("d", 0.6)]]
    fake_verify.queue = [
        None if verdicts[key] is None else Verdict(verdict=verdicts[key], reasons=[], confidence=0.5)
        for key in ["a", "b", "c", "d"]
    ]
    monkeypatch.setattr("matching.verifier.verify_pair", fake_verify)
    ranked = rerank(report, scored, 10)
    # likely_same > possibly_same > no verdict > different
    assert [row["listing_id"] for row in ranked] == ["c", "b", "d", "a"]


def test_ties_fall_back_to_stage_two_score(monkeypatch, report):
    monkeypatch.setattr(
        "matching.verifier.verify_pair",
        lambda a, b: Verdict(verdict="possibly_same", reasons=[], confidence=0.5),
    )
    scored = [item("low", 0.2), item("high", 0.9), item("mid", 0.5)]
    ranked = rerank(report, scored, 10)
    assert [row["listing_id"] for row in ranked] == ["high", "mid", "low"]


def test_numeric_score_is_not_modified_by_rerank(monkeypatch, report):
    monkeypatch.setattr(
        "matching.verifier.verify_pair",
        lambda a, b: Verdict(verdict="likely_same", reasons=[], confidence=0.9),
    )
    ranked = rerank(report, [item("L1", 0.42)], 10)
    assert ranked[0]["score"] == 0.42


def test_verdict_confidence_is_clamped():
    assert Verdict(verdict="likely_same", confidence=5).confidence == 1.0
    assert Verdict(verdict="likely_same", confidence=-3).confidence == 0.0
    assert Verdict(verdict="likely_same", confidence="oops").confidence == 0.0


def test_verdict_reasons_coerced_from_string():
    assert Verdict(verdict="different", reasons="only one").reasons == ["only one"]
    assert Verdict(verdict="different", reasons=None).reasons == []


def test_verify_pair_returns_none_when_no_readable_photos():
    from matching.verifier import verify_pair

    assert verify_pair([], []) is None
