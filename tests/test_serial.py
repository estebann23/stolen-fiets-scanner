"""SPEC 5.2 / 7.2 stage 1: serial normalisation, OCR confusables, text extraction."""

from __future__ import annotations

import pytest

from enrichment.serial_ocr import (
    extract_serial,
    extract_serial_from_text,
    normalise_serial,
)
from matching.filters import canonical_serial, serial_matches


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("gz 1234-5678", "GZ12345678"),
        ("GZ12345678", "GZ12345678"),
        ("  gz/1234.5678  ", "GZ12345678"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalise_serial_keeps_only_alnum_uppercase(raw, expected):
    assert normalise_serial(raw) == expected


def test_canonical_serial_applies_full_ocr_map():
    # SPEC: O->0, I->1, L->1, S->5, B->8
    assert canonical_serial("OILSB") == "01158"


def test_canonical_serial_is_idempotent():
    once = canonical_serial("GZO123S")
    assert canonical_serial(once) == once


@pytest.mark.parametrize(
    "left,right",
    [
        ("GZO123", "GZ0123"),
        ("gz-o12 3", "GZ0123"),
        ("ABIL", "AB11"),
        ("SB", "58"),
    ],
)
def test_serial_matches_through_ocr_confusables(left, right):
    assert serial_matches(left, right) is True


@pytest.mark.parametrize(
    "left,right",
    [
        (None, "GZ0123"),
        ("GZ0123", None),
        ("", "GZ0123"),
        ("GZ0123", "GZ9999"),
    ],
)
def test_serial_matches_rejects_missing_or_different(left, right):
    assert serial_matches(left, right) is False


def test_extract_serial_from_text_keyword_anchored():
    assert extract_serial_from_text("Framenummer GZ12345678.") == "GZ12345678"
    assert extract_serial_from_text("Serienummer: ab-1234-cd") == "AB1234CD"
    assert extract_serial_from_text("serial 12345678") == "12345678"


def test_extract_serial_from_text_ignores_unanchored_numbers():
    assert extract_serial_from_text("Nette stadsfiets, weinig gebruikt, 28 inch.") is None
    assert extract_serial_from_text("Prijs 12345678 euro") is None
    assert extract_serial_from_text("") is None


def test_extract_serial_from_text_rejects_too_short_tokens():
    # normalised length must be 6..20
    assert extract_serial_from_text("Framenummer AB12") is None


def test_extract_serial_prefers_text_over_photos(monkeypatch):
    monkeypatch.setattr(
        "enrichment.serial_ocr.extract_serial_from_images",
        lambda paths: pytest.fail("should not call the VLM when text already has a serial"),
    )
    assert extract_serial([], "Framenummer GZ12345678.") == "GZ12345678"


def test_extract_serial_from_images_skipped_when_no_photos():
    assert extract_serial([], "geen nummer hier") is None
