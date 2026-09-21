"""SPEC 7.2 stage 2: 0.45/0.30/0.15/0.10 weights, no renormalisation, serial override."""

from __future__ import annotations

import numpy as np
import pytest

from config import MATCH_WEIGHTS
from enrichment.attributes import BikeAttributes
from matching.scorer import (
    attribute_agreement,
    image_similarity,
    mark_overlap,
    score_candidate,
    text_similarity,
)
from tests.conftest import unit


def test_spec_weights_are_unchanged():
    assert MATCH_WEIGHTS == {"image": 0.45, "attributes": 0.30, "marks": 0.15, "text": 0.10}
    assert sum(MATCH_WEIGHTS.values()) == pytest.approx(1.0)


def test_image_similarity_identical_is_one(vec_a):
    assert image_similarity(vec_a, vec_a) == pytest.approx(1.0, abs=1e-6)


def test_image_similarity_orthogonal_is_zero(vec_a, vec_b):
    assert image_similarity(vec_a, vec_b) == pytest.approx(0.0, abs=1e-6)


def test_image_similarity_takes_the_max_over_all_pairs(vec_a, vec_b):
    listing = np.stack([vec_b, vec_a])
    report = np.stack([vec_b])
    assert image_similarity(report, listing) == pytest.approx(1.0, abs=1e-6)


def test_image_similarity_empty_sides_are_zero(vec_a):
    assert image_similarity(np.zeros((0, 0), dtype=np.float32), vec_a) == 0.0
    assert image_similarity(vec_a, np.zeros((0, 0), dtype=np.float32)) == 0.0
    assert image_similarity(None, vec_a) == 0.0


def test_image_similarity_never_negative(vec_a):
    assert image_similarity(vec_a, -vec_a) == 0.0


def test_attribute_agreement_all_fields_match():
    attrs = BikeAttributes(
        brand="Gazelle",
        model="Orange C7",
        bike_type="city",
        frame_shape="low-step",
        colors=["black"],
        accessories=["rear rack"],
    )
    listing = {
        "brand": "gazelle",
        "model": "orange c7",
        "bike_type": "city",
        "frame_shape": "low-step",
        "colors": ["black"],
        "accessories": ["rear rack"],
    }
    assert attribute_agreement(attrs, listing) == pytest.approx(1.0)


def test_attribute_agreement_ignores_fields_missing_on_either_side():
    attrs = BikeAttributes(brand="Gazelle")
    # only brand is comparable, and it matches
    assert attribute_agreement(attrs, {"brand": "Gazelle", "model": None}) == pytest.approx(1.0)
    assert attribute_agreement(attrs, {"brand": "Batavus"}) == pytest.approx(0.0)


def test_attribute_agreement_with_no_comparable_fields_is_zero():
    assert attribute_agreement(BikeAttributes(), {"brand": "Gazelle"}) == 0.0
    assert attribute_agreement(None, {"brand": "Gazelle"}) == 0.0
    assert attribute_agreement(BikeAttributes(brand="Gazelle"), None) == 0.0


def test_attribute_agreement_uses_jaccard_for_lists():
    attrs = BikeAttributes(colors=["black", "grey"])
    # {black, grey} vs {black, blue}: intersection 1, union 3
    assert attribute_agreement(attrs, {"colors": ["black", "blue"]}) == pytest.approx(1 / 3)
    assert attribute_agreement(attrs, {"colors": ["black", "grey"]}) == pytest.approx(1.0)


def test_mark_overlap_exact_and_partial():
    assert mark_overlap(["scratch on top tube"], ["scratch on top tube"]) == pytest.approx(1.0)
    assert mark_overlap(None, ["x"]) == 0.0
    assert mark_overlap([], []) == 0.0
    assert mark_overlap(["red sticker"], ["blue dent"]) == pytest.approx(0.0)


def test_text_similarity_requires_matching_dimensions(vec_a):
    assert text_similarity(vec_a, vec_a) == pytest.approx(1.0, abs=1e-6)
    assert text_similarity(vec_a, unit(1.0, 0.0)) == 0.0
    assert text_similarity(None, vec_a) == 0.0


def test_score_is_the_exact_spec_weighted_sum(vec_a):
    attrs = BikeAttributes(brand="Gazelle")
    score, parts = score_candidate(
        report_vecs=vec_a,
        listing_vecs=vec_a,
        report_attrs=attrs,
        listing_attrs={"brand": "Gazelle"},
        report_text_vec=vec_a,
        listing_text_vec=vec_a,
        serial_hit=False,
    )
    expected = 0.45 * parts["image"] + 0.30 * parts["attributes"] + 0.15 * parts["marks"] + 0.10 * parts["text"]
    assert score == pytest.approx(expected)
    assert score == pytest.approx(0.85, abs=1e-5)  # image 1, attrs 1, marks 0, text 1


def test_missing_modalities_are_not_renormalised(vec_a):
    """Image-only perfect match must cap at 0.45, never rescale to 1.0."""
    score, parts = score_candidate(
        report_vecs=vec_a,
        listing_vecs=vec_a,
        report_attrs=None,
        listing_attrs=None,
        report_text_vec=None,
        listing_text_vec=None,
        serial_hit=False,
    )
    assert parts["image"] == pytest.approx(1.0, abs=1e-6)
    assert score == pytest.approx(0.45, abs=1e-6)


def test_serial_hit_forces_score_one(vec_a, vec_b):
    score, _ = score_candidate(
        report_vecs=vec_a,
        listing_vecs=vec_b,  # nothing else agrees
        report_attrs=None,
        listing_attrs=None,
        report_text_vec=None,
        listing_text_vec=None,
        serial_hit=True,
    )
    assert score == 1.0


def test_suspicion_score_never_influences_the_match_score(vec_a):
    """SPEC hard rule: suspicion_score is display-only."""
    base, _ = score_candidate(
        report_vecs=vec_a,
        listing_vecs=vec_a,
        report_attrs=BikeAttributes(brand="Gazelle"),
        listing_attrs={"brand": "Gazelle"},
        report_text_vec=vec_a,
        listing_text_vec=vec_a,
        serial_hit=False,
    )
    for suspicion in (0.0, 0.5, 1.0, 999.0):
        other, _ = score_candidate(
            report_vecs=vec_a,
            listing_vecs=vec_a,
            report_attrs=BikeAttributes(brand="Gazelle"),
            listing_attrs={"brand": "Gazelle", "suspicion_score": suspicion},
            report_text_vec=vec_a,
            listing_text_vec=vec_a,
            serial_hit=False,
        )
        assert other == pytest.approx(base)


def test_scorer_never_looks_up_a_suspicion_field():
    """Static guard on the hard rule: scorer reads no suspicion key or attribute."""
    import ast
    import inspect

    import matching.scorer as scorer

    looked_up: set[str] = set()
    for node in ast.walk(ast.parse(inspect.getsource(scorer))):
        if isinstance(node, ast.Attribute):
            looked_up.add(node.attr)
        elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            looked_up.add(str(node.slice.value))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
        ):
            looked_up.update(str(arg.value) for arg in node.args if isinstance(arg, ast.Constant))
    assert [name for name in looked_up if "suspicion" in name.lower()] == []


def test_score_is_clamped_to_unit_interval(vec_a):
    score, _ = score_candidate(
        report_vecs=vec_a,
        listing_vecs=vec_a,
        report_attrs=BikeAttributes(brand="Gazelle", marks=["scratch"]),
        listing_attrs={"brand": "Gazelle", "marks": ["scratch"]},
        report_text_vec=vec_a,
        listing_text_vec=vec_a,
        serial_hit=False,
    )
    assert 0.0 <= score <= 1.0
