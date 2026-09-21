"""Shared fixtures: isolated SQLite, synthetic vectors, and offline VLM stubs.

No test may touch the real data/bike.db, the network, or the CLIP weights.
"""

from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import db as db_module


@pytest.fixture
def tmp_db(tmp_path, monkeypatch) -> Path:
    """Point every db.connect() at a throwaway database."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", path)
    db_module.init_schema()
    return path


@pytest.fixture
def conn(tmp_db) -> sqlite3.Connection:
    connection = db_module.connect()
    yield connection
    connection.close()


def unit(*values: float) -> np.ndarray:
    vec = np.asarray(values, dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    return (vec / norm).astype(np.float32) if norm else vec


@pytest.fixture
def vec_a() -> np.ndarray:
    return unit(1.0, 0.0, 0.0, 0.0)


@pytest.fixture
def vec_b() -> np.ndarray:
    return unit(0.0, 1.0, 0.0, 0.0)


def jpeg_bytes(color: tuple[int, int, int] = (10, 120, 200), size=(64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


def png_bytes(color: tuple[int, int, int] = (200, 10, 10), size=(64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, color + (255,)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def photo_jpeg() -> bytes:
    return jpeg_bytes()


@pytest.fixture
def photo_png() -> bytes:
    return png_bytes()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Hard-fail any test that tries to reach a real VLM endpoint."""

    def _boom(*args, **kwargs):  # pragma: no cover - only fires on a bug
        raise AssertionError("test attempted a live VLM call")

    monkeypatch.setattr("enrichment.llm_client.call_vlm_json", _boom, raising=False)
    monkeypatch.setattr("enrichment.attributes.call_vlm_json", _boom, raising=False)
    monkeypatch.setattr("enrichment.serial_ocr.call_vlm_json", _boom, raising=False)
    monkeypatch.setattr("matching.verifier.call_vlm_json", _boom, raising=False)
