"""Weighted similarity score (image, attributes, marks, text).

suspicion_score is NEVER read here (SPEC hard rule).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from config import MATCH_WEIGHTS
from enrichment.attributes import BikeAttributes


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _norm_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _as_list(value: Any) -> list[str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return None


def _jaccard(left: list[str], right: list[str]) -> float:
    a = {item.strip().lower() for item in left if item and str(item).strip()}
    b = {item.strip().lower() for item in right if item and str(item).strip()}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def image_similarity(report_vecs: np.ndarray, listing_vecs: np.ndarray) -> float:
    if report_vecs is None or listing_vecs is None:
        return 0.0
    report = np.asarray(report_vecs, dtype=np.float32)
    listing = np.asarray(listing_vecs, dtype=np.float32)
    if report.size == 0 or listing.size == 0:
        return 0.0
    if report.ndim == 1:
        report = report.reshape(1, -1)
    if listing.ndim == 1:
        listing = listing.reshape(1, -1)
    sims = listing @ report.T
    return _clamp01(float(np.max(sims)))


def attribute_agreement(
    report_attrs: BikeAttributes | None,
    listing_attrs: dict[str, Any] | None,
) -> float:
    if report_attrs is None or not listing_attrs:
        return 0.0
    scores: list[float] = []

    def _exact(report_value: Any, listing_value: Any) -> None:
        left = _norm_str(report_value)
        right = _norm_str(listing_value)
        if left is None or right is None:
            return
        scores.append(1.0 if left == right else 0.0)

    _exact(report_attrs.brand, listing_attrs.get("brand"))
    _exact(report_attrs.model, listing_attrs.get("model"))
    _exact(report_attrs.bike_type, listing_attrs.get("bike_type"))
    _exact(report_attrs.frame_shape, listing_attrs.get("frame_shape"))

    report_colors = _as_list(report_attrs.colors)
    listing_colors = _as_list(listing_attrs.get("colors"))
    if report_colors is not None and listing_colors is not None:
        scores.append(_jaccard(report_colors, listing_colors))

    report_acc = _as_list(report_attrs.accessories)
    listing_acc = _as_list(listing_attrs.get("accessories"))
    if report_acc is not None and listing_acc is not None:
        scores.append(_jaccard(report_acc, listing_acc))

    if not scores:
        return 0.0
    return _clamp01(float(sum(scores) / len(scores)))


def _mark_tokens(marks: list[str] | None) -> set[str]:
    tokens: set[str] = set()
    for mark in marks or []:
        text = str(mark).strip().lower()
        if not text:
            continue
        tokens.add(text)
        tokens.update(part for part in text.replace(",", " ").split() if part)
    return tokens


def mark_overlap(report_marks: list[str] | None, listing_marks: list[str] | None) -> float:
    if not report_marks or not listing_marks:
        return 0.0
    left = _mark_tokens(report_marks)
    right = _mark_tokens(listing_marks)
    if not left or not right:
        return 0.0
    substring_hits = 0
    for token in left:
        if any(token in other or other in token for other in right):
            substring_hits += 1
    union = len(left | right)
    if union == 0:
        return 0.0
    return _clamp01(substring_hits / union)


def text_similarity(
    report_text_vec: np.ndarray | None,
    listing_text_vec: np.ndarray | None,
) -> float:
    if report_text_vec is None or listing_text_vec is None:
        return 0.0
    report = np.asarray(report_text_vec, dtype=np.float32).reshape(-1)
    listing = np.asarray(listing_text_vec, dtype=np.float32).reshape(-1)
    if report.size == 0 or listing.size == 0 or report.shape != listing.shape:
        return 0.0
    return _clamp01(float(np.dot(report, listing)))


def score_candidate(
    *,
    report_vecs: np.ndarray,
    listing_vecs: np.ndarray,
    report_attrs: BikeAttributes | None,
    listing_attrs: dict[str, Any] | None,
    report_text_vec: np.ndarray | None,
    listing_text_vec: np.ndarray | None,
    serial_hit: bool,
) -> tuple[float, dict[str, float]]:
    img = image_similarity(report_vecs, listing_vecs)
    attr = attribute_agreement(report_attrs, listing_attrs)
    marks = mark_overlap(
        None if report_attrs is None else report_attrs.marks,
        None if not listing_attrs else _as_list(listing_attrs.get("marks")),
    )
    text = text_similarity(report_text_vec, listing_text_vec)
    components = {
        "image": img,
        "attributes": attr,
        "marks": marks,
        "text": text,
    }
    if serial_hit:
        return 1.0, components
    weights = MATCH_WEIGHTS
    score = (
        float(weights["image"]) * img
        + float(weights["attributes"]) * attr
        + float(weights["marks"]) * marks
        + float(weights["text"]) * text
    )
    return _clamp01(score), components


def main() -> None:
    vec = np.array([0.0, 1.0], dtype=np.float32)
    print("self", image_similarity(vec.reshape(1, -1), vec.reshape(1, -1)))
    score, parts = score_candidate(
        report_vecs=vec.reshape(1, -1),
        listing_vecs=vec.reshape(1, -1),
        report_attrs=None,
        listing_attrs=None,
        report_text_vec=vec,
        listing_text_vec=vec,
        serial_hit=False,
    )
    print("score", score, "parts", parts)


if __name__ == "__main__":
    main()
