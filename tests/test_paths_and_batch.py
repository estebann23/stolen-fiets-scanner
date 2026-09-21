"""Relative-path resolution (SPEC 6: posix relative paths) and batch enrichment (SPEC 5.2)."""

from __future__ import annotations

import os

import pytest

import enrichment.run_enrichment as batch
import matching.verifier as verifier
from tests.conftest import jpeg_bytes


def test_verify_pair_resolves_db_relative_paths_from_any_cwd(tmp_path, monkeypatch):
    """DB paths are relative to the repo root, so the verifier must not depend on os.getcwd()."""
    root = tmp_path / "repo"
    (root / "data" / "reports" / "r_1").mkdir(parents=True)
    (root / "data" / "images" / "m1").mkdir(parents=True)
    (root / "data" / "reports" / "r_1" / "0.jpg").write_bytes(jpeg_bytes())
    (root / "data" / "images" / "m1" / "0.jpg").write_bytes(jpeg_bytes())

    monkeypatch.setattr(verifier, "ROOT", root, raising=False)
    seen: dict[str, int] = {}
    monkeypatch.setattr(
        verifier,
        "call_vlm_json",
        lambda system, user, paths: seen.update(n=len(paths)) or {"verdict": "possibly_same"},
    )

    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    result = verifier.verify_pair(["data/reports/r_1/0.jpg"], ["data/images/m1/0.jpg"])
    assert result is not None, "verifier silently skipped photos because cwd != repo root"
    assert seen["n"] == 2


def test_rerank_passes_report_photos_to_the_verifier(tmp_path, monkeypatch):
    captured: list[list] = []
    monkeypatch.setattr(
        verifier,
        "verify_pair",
        lambda report_paths, listing_paths: captured.append([report_paths, listing_paths]) or None,
    )
    report = {"id": "r_1", "images": ["data/reports/r_1/0.jpg"]}
    scored = [{"listing_id": "m1", "score": 0.5, "listing": {"image_paths": ["data/images/m1/0.jpg"]}}]
    verifier.rerank(report, scored, 10)
    assert captured[0][0] == [__import__("pathlib").Path("data/reports/r_1/0.jpg")]
    assert captured[0][1] == [__import__("pathlib").Path("data/images/m1/0.jpg")]


# ---------------------------------------------------------------- run_enrichment


@pytest.fixture
def batch_db(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "EMB_CACHE_DIR", tmp_path / "emb")
    for listing_id in ("l1", "l2"):
        conn.execute(
            "INSERT INTO listings (id, description, price, seller_id) VALUES (?, 'nette fiets', 300.0, 's1')",
            (listing_id,),
        )
        conn.execute(
            "INSERT INTO listing_images (listing_id, path) VALUES (?, ?)",
            (listing_id, f"data/images/{listing_id}/0.jpg"),
        )
    conn.commit()
    return conn


def test_run_batch_reports_done_counts_per_step(batch_db, monkeypatch):
    monkeypatch.setattr(batch, "enrich_listing", lambda conn, lid, force=False: None)
    monkeypatch.setattr(batch, "embed_listing_images", lambda conn, lid, force=False: 1)
    monkeypatch.setattr(batch, "embed_description_cached", lambda lid, text, force=False: None)
    monkeypatch.setattr(batch, "enrich_listing_serial", lambda conn, lid, force=False: None)

    counts = batch.run_batch()
    assert counts["attributes"]["done"] == 2
    assert counts["embeddings"]["done"] == 2
    assert counts["serial"]["done"] == 2
    assert counts["risk"]["done"] == 2
    assert all(step["failed"] == 0 for step in counts.values())


def test_run_batch_only_runs_the_requested_step(batch_db, monkeypatch):
    monkeypatch.setattr(
        batch, "enrich_listing", lambda *a, **k: pytest.fail("attributes must be skipped")
    )
    monkeypatch.setattr(batch, "embed_listing_images", lambda conn, lid, force=False: 1)
    monkeypatch.setattr(batch, "embed_description_cached", lambda lid, text, force=False: None)
    counts = batch.run_batch(only="embeddings")
    assert counts["embeddings"]["done"] == 2
    assert counts["attributes"]["done"] == 0
    assert counts["risk"]["done"] == 0


def test_run_batch_limit_caps_the_listing_set(batch_db, monkeypatch):
    monkeypatch.setattr(batch, "embed_listing_images", lambda conn, lid, force=False: 1)
    monkeypatch.setattr(batch, "embed_description_cached", lambda lid, text, force=False: None)
    counts = batch.run_batch(only="embeddings", limit=1)
    assert counts["embeddings"]["done"] == 1


def test_run_batch_skips_already_enriched_rows(batch_db, monkeypatch):
    batch_db.execute("INSERT INTO listing_attributes (listing_id, brand) VALUES ('l1', 'Gazelle')")
    batch_db.commit()
    monkeypatch.setattr(batch, "enrich_listing", lambda conn, lid, force=False: None)
    counts = batch.run_batch(only="attributes")
    assert counts["attributes"]["skipped"] == 1
    assert counts["attributes"]["done"] == 1


def test_run_batch_records_failures_without_aborting(batch_db, monkeypatch):
    def boom(conn, lid, force=False):
        raise RuntimeError("vlm down")

    monkeypatch.setattr(batch, "enrich_listing", boom)
    counts = batch.run_batch(only="attributes")
    assert counts["attributes"]["failed"] == 2
    assert counts["attributes"]["done"] == 0


def test_eval_scripts_are_still_unimplemented_stubs():
    """SPEC 10 lists these as not done; this test flips when they get built."""
    import eval.evaluate as evaluate
    import eval.make_test_reports as make_test_reports

    with pytest.raises(NotImplementedError):
        evaluate.main()
    with pytest.raises(NotImplementedError):
        make_test_reports.main()
