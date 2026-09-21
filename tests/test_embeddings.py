"""SPEC 5.2: blob roundtrip, disk-cached text vectors, ImageIndex max-cosine query."""

from __future__ import annotations

import numpy as np
import pytest

import enrichment.embeddings as emb
from enrichment.embeddings import ImageIndex, blob_to_vec, vec_to_blob
from tests.conftest import unit


def test_vector_blob_roundtrip_is_lossless():
    vec = unit(0.1, -0.2, 0.3, 0.9)
    assert np.allclose(blob_to_vec(vec_to_blob(vec)), vec, atol=1e-7)


def test_blob_to_vec_returns_a_writable_copy():
    vec = unit(1.0, 0.0)
    out = blob_to_vec(vec_to_blob(vec))
    out[0] = 0.5  # must not raise on a read-only buffer
    assert out[0] == pytest.approx(0.5)


def test_l2_normalize_handles_the_zero_vector():
    zeros = np.zeros(4, dtype=np.float32)
    assert np.allclose(emb._l2_normalize(zeros), zeros)


def test_l2_normalize_produces_unit_length():
    out = emb._l2_normalize(np.array([3.0, 4.0], dtype=np.float32))
    assert float(np.linalg.norm(out)) == pytest.approx(1.0, abs=1e-6)


def test_image_index_empty_db_returns_no_results(conn):
    index = ImageIndex.build_from_db(conn)
    assert index.query(unit(1.0, 0.0), top_k=5) == []


def test_image_index_returns_max_cosine_per_listing(conn):
    a = unit(1.0, 0.0, 0.0, 0.0)
    b = unit(0.0, 1.0, 0.0, 0.0)
    mixed = unit(1.0, 1.0, 0.0, 0.0)
    conn.execute("INSERT INTO listings (id) VALUES ('l1'), ('l2')")
    rows = [("l1", "a0.jpg", a), ("l1", "a1.jpg", mixed), ("l2", "b0.jpg", b)]
    for listing_id, path, vec in rows:
        conn.execute(
            "INSERT INTO listing_images (listing_id, path, clip_vec) VALUES (?, ?, ?)",
            (listing_id, path, vec_to_blob(vec)),
        )
    conn.commit()

    index = ImageIndex.build_from_db(conn)
    results = dict(index.query(a, top_k=10))
    # l1 has an exact photo match, so its best cosine is 1.0 (not the average)
    assert results["l1"] == pytest.approx(1.0, abs=1e-6)
    assert results["l2"] == pytest.approx(0.0, abs=1e-6)
    assert index.query(a, top_k=1)[0][0] == "l1"


def test_image_index_skips_rows_without_vectors(conn):
    conn.execute("INSERT INTO listings (id) VALUES ('l1')")
    conn.execute("INSERT INTO listing_images (listing_id, path) VALUES ('l1', 'a.jpg')")
    conn.commit()
    assert ImageIndex.build_from_db(conn).query(unit(1.0, 0.0), top_k=5) == []


def test_embed_description_cached_writes_and_reuses_the_npy(tmp_path, monkeypatch):
    calls: list[str] = []

    def fake_embed_text(text: str):
        calls.append(text)
        return unit(1.0, 2.0, 3.0, 4.0)

    monkeypatch.setattr(emb, "EMB_CACHE_DIR", tmp_path)
    monkeypatch.setattr(emb, "embed_text", fake_embed_text)

    first = emb.embed_description_cached("l1", "een nette stadsfiets")
    assert (tmp_path / "text" / "l1.npy").is_file()
    second = emb.embed_description_cached("l1", "een nette stadsfiets")
    assert calls == ["een nette stadsfiets"]  # second call served from disk
    assert np.allclose(first, second, atol=1e-6)


def test_embed_description_cached_force_recomputes(tmp_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(emb, "EMB_CACHE_DIR", tmp_path)
    monkeypatch.setattr(emb, "embed_text", lambda t: (calls.append(t), unit(1.0, 0.0))[1])
    emb.embed_description_cached("l1", "a")
    emb.embed_description_cached("l1", "a", force=True)
    assert len(calls) == 2


def test_cached_text_vectors_are_returned_l2_normalised(tmp_path, monkeypatch):
    monkeypatch.setattr(emb, "EMB_CACHE_DIR", tmp_path)
    monkeypatch.setattr(emb, "embed_text", lambda t: np.array([3.0, 4.0], dtype=np.float32))
    emb.embed_description_cached("l1", "a")
    cached = emb.embed_description_cached("l1", "a")
    assert float(np.linalg.norm(cached)) == pytest.approx(1.0, abs=1e-6)


def test_embed_listing_images_is_idempotent(conn, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(emb, "embed_image", lambda p: (calls.append(str(p)), unit(1.0, 0.0))[1])
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    conn.execute("INSERT INTO listings (id) VALUES ('l1')")
    conn.execute("INSERT INTO listing_images (listing_id, path) VALUES ('l1', 'data/images/l1/0.jpg')")
    conn.commit()

    assert emb.embed_listing_images(conn, "l1") == 1
    assert emb.embed_listing_images(conn, "l1") == 0  # skip-if-done
    assert emb.embed_listing_images(conn, "l1", force=True) == 1
    assert len(calls) == 2


def test_embed_entity_images_rejects_unknown_tables(conn):
    with pytest.raises(ValueError):
        emb._embed_entity_images(
            conn, table="listings; DROP TABLE listings", fk_column="listing_id",
            entity_id="l1", force=False,
        )
