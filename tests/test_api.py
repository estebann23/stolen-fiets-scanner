"""SPEC 7-8: intake validation, gazetteer, EXIF stripping, match + cached-match routes."""

from __future__ import annotations

import io
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import db as db_module
from config import RESULT_TOP_K
from enrichment.attributes import BikeAttributes
from enrichment.embeddings import vec_to_blob
from tests.conftest import jpeg_bytes, png_bytes, unit

REPORT_VEC = unit(1.0, 0.0, 0.0, 0.0)
OTHER_VEC = unit(0.0, 1.0, 0.0, 0.0)
TEXT_VEC = unit(0.0, 0.0, 1.0, 0.0)


@pytest.fixture
def client(tmp_path, monkeypatch, tmp_db):
    """App wired to a temp DB and temp data root, with CLIP and the VLM stubbed out."""
    import api.routes.reports as reports

    root = tmp_path.resolve()
    monkeypatch.setattr(reports, "ROOT", root)
    monkeypatch.setattr(reports, "REPORTS_DIR", root / "data" / "reports")

    def fake_embed_report_images(conn, report_id, *, force=False):
        rows = conn.execute(
            "SELECT id FROM report_images WHERE report_id = ? ORDER BY id", (report_id,)
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE report_images SET clip_vec = ? WHERE id = ?",
                (vec_to_blob(REPORT_VEC), row["id"]),
            )
        conn.commit()
        return len(rows)

    monkeypatch.setattr(reports, "embed_report_images", fake_embed_report_images)
    monkeypatch.setattr(reports, "embed_description_cached", lambda eid, text, **kw: TEXT_VEC)
    monkeypatch.setattr(reports, "extract_attributes", lambda paths, desc: BikeAttributes(brand="Gazelle"))
    monkeypatch.setattr("matching.verifier.verify_pair", lambda a, b: None)

    from api.main import app

    with TestClient(app) as test_client:
        yield test_client


def post_report(client, *, photos=None, **fields):
    files = photos if photos is not None else [("photos", ("bike.jpg", jpeg_bytes(), "image/jpeg"))]
    data = {"stolen_at": "2026-09-01"}
    data.update({key: value for key, value in fields.items() if value is not None})
    return client.post("/reports", files=files, data=data)


def seed_listing(listing_id, *, vec=None, **columns):
    conn = db_module.connect()
    try:
        db_module.upsert_listing(
            conn,
            {
                "id": listing_id,
                "title": columns.get("title", f"bike {listing_id}"),
                "description": columns.get("description", "nette stadsfiets"),
                "price": columns.get("price", 300.0),
                "lat": columns.get("lat"),
                "lon": columns.get("lon"),
                "posted_at": columns.get("posted_at"),
                "seller_id": columns.get("seller_id", "s1"),
                "url": columns.get("url", f"https://example.invalid/{listing_id}"),
                "suspicion_score": columns.get("suspicion_score", 0.2),
                "image_paths": [f"data/images/{listing_id}/0.jpg"],
            },
        )
        if columns.get("serial_found") or columns.get("brand"):
            conn.execute(
                "INSERT INTO listing_attributes (listing_id, brand, serial_found) VALUES (?, ?, ?)",
                (listing_id, columns.get("brand"), columns.get("serial_found")),
            )
        if vec is not None:
            conn.execute(
                "UPDATE listing_images SET clip_vec = ? WHERE listing_id = ?",
                (vec_to_blob(vec), listing_id),
            )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------- health


def test_health_reports_the_corpus_size(client):
    assert client.get("/health").json() == {"status": "ok", "listings": 0}
    seed_listing("m1")
    assert client.get("/health").json() == {"status": "ok", "listings": 1}


# -------------------------------------------------------------------- listings


def test_listing_detail_returns_the_spec_shape(client):
    seed_listing("m1", brand="Gazelle", serial_found="GZ123456")
    body = client.get("/listings/m1").json()
    assert body["id"] == "m1"
    assert body["images"] == ["data/images/m1/0.jpg"]
    assert body["attributes"]["brand"] == "Gazelle"
    assert body["suspicion_score"] == pytest.approx(0.2)


def test_unknown_listing_is_404(client):
    assert client.get("/listings/nope").status_code == 404


# ---------------------------------------------------------------------- intake


def test_report_intake_returns_201_and_a_prefixed_id(client):
    response = post_report(client)
    assert response.status_code == 201
    assert re.fullmatch(r"r_[0-9a-f]{8}", response.json()["report_id"])


def test_five_photos_are_accepted(client):
    photos = [("photos", (f"{i}.jpg", jpeg_bytes(), "image/jpeg")) for i in range(5)]
    assert post_report(client, photos=photos).status_code == 201


def test_six_photos_are_rejected(client):
    photos = [("photos", (f"{i}.jpg", jpeg_bytes(), "image/jpeg")) for i in range(6)]
    assert post_report(client, photos=photos).status_code == 422


def test_zero_photos_are_rejected(client):
    assert client.post("/reports", data={"stolen_at": "2026-09-01"}).status_code == 422


@pytest.mark.parametrize("name,mime", [("bike.png", "image/png"), ("bike.webp", "image/webp")])
def test_png_and_webp_are_accepted(client, name, mime):
    payload = png_bytes() if name.endswith(".png") else jpeg_bytes()
    photos = [("photos", (name, payload, mime))]
    assert post_report(client, photos=photos).status_code == 201


def test_non_image_extensions_are_rejected(client):
    photos = [("photos", ("payload.exe", b"MZ\x00\x00", "application/octet-stream"))]
    assert post_report(client, photos=photos).status_code == 422


def test_corrupt_image_body_is_rejected(client):
    photos = [("photos", ("bike.jpg", b"not an image at all", "image/jpeg"))]
    assert post_report(client, photos=photos).status_code == 422


def test_missing_stolen_at_is_rejected(client):
    files = [("photos", ("bike.jpg", jpeg_bytes(), "image/jpeg"))]
    assert client.post("/reports", files=files).status_code == 422


def test_malformed_stolen_at_is_rejected(client):
    files = [("photos", ("bike.jpg", jpeg_bytes(), "image/jpeg"))]
    response = client.post("/reports", files=files, data={"stolen_at": "last tuesday"})
    assert response.status_code == 422


def test_stolen_at_accepts_date_and_datetime_and_z_suffix(client):
    for value in ("2026-09-01", "2026-09-01T13:45:00", "2026-09-01T13:45:00Z"):
        files = [("photos", ("bike.jpg", jpeg_bytes(), "image/jpeg"))]
        assert client.post("/reports", files=files, data={"stolen_at": value}).status_code == 201


def test_known_city_resolves_through_the_offline_gazetteer(client):
    report_id = post_report(client, location="Maastricht").json()["report_id"]
    row = db_module.fetch_report(report_id)
    assert row["stolen_lat"] == pytest.approx(50.8483)
    assert row["stolen_lon"] == pytest.approx(5.6886)


def test_gazetteer_lookup_is_case_and_accent_tolerant(client):
    report_id = post_report(client, location="  liÈge ").json()["report_id"]
    assert db_module.fetch_report(report_id)["stolen_lat"] == pytest.approx(50.6333)


def test_unknown_city_yields_null_coords_not_422(client):
    response = post_report(client, location="Atlantis")
    assert response.status_code == 201
    row = db_module.fetch_report(response.json()["report_id"])
    assert row["stolen_lat"] is None and row["stolen_lon"] is None


def test_explicit_coords_win_over_the_location_string(client):
    report_id = post_report(client, location="Maastricht", stolen_lat="51.5", stolen_lon="4.5").json()[
        "report_id"
    ]
    row = db_module.fetch_report(report_id)
    assert row["stolen_lat"] == pytest.approx(51.5)


def test_photos_are_reencoded_to_rgb_jpeg(client, tmp_path):
    photos = [("photos", ("bike.png", png_bytes(), "image/png"))]
    report_id = post_report(client, photos=photos).json()["report_id"]
    row = db_module.fetch_report(report_id)
    assert row["images"] == [f"data/reports/{report_id}/0.jpg"]
    saved = tmp_path / row["images"][0]
    with Image.open(saved) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"


def test_exif_is_stripped_from_stored_photos(client, tmp_path):
    source = Image.new("RGB", (48, 48), (10, 20, 30))
    exif = source.getexif()
    exif[0x0112] = 6  # Orientation
    exif[0x010F] = "SecretCamera"  # Make
    buffer = io.BytesIO()
    source.save(buffer, format="JPEG", exif=exif)
    assert Image.open(io.BytesIO(buffer.getvalue())).getexif()  # sanity: input has EXIF

    photos = [("photos", ("bike.jpg", buffer.getvalue(), "image/jpeg"))]
    report_id = post_report(client, photos=photos).json()["report_id"]
    saved = tmp_path / f"data/reports/{report_id}/0.jpg"
    with Image.open(saved) as image:
        assert dict(image.getexif()) == {}


def test_intake_survives_a_vlm_outage(client, monkeypatch):
    import api.routes.reports as reports

    def boom(*args, **kwargs):
        raise RuntimeError("openrouter is down")

    monkeypatch.setattr(reports, "extract_attributes", boom)
    response = post_report(client)
    assert response.status_code == 201
    report_id = response.json()["report_id"]
    conn = db_module.connect()
    vecs = conn.execute(
        "SELECT clip_vec FROM report_images WHERE report_id = ?", (report_id,)
    ).fetchall()
    conn.close()
    assert all(row["clip_vec"] is not None for row in vecs)  # embeddings still persisted


def test_optional_fields_are_persisted(client):
    report_id = post_report(
        client,
        serial="GZ-1234-56",
        brand="Gazelle",
        color="black",
        notes="rear rack",
        police_report_nr="PL-99",
    ).json()["report_id"]
    row = db_module.fetch_report(report_id)
    assert row["serial"] == "GZ-1234-56"
    assert row["brand"] == "Gazelle"
    assert row["color"] == "black"
    assert row["notes"] == "rear rack"
    assert row["police_report_nr"] == "PL-99"


# --------------------------------------------------------------------- matching


def test_match_on_unknown_report_is_404(client):
    assert client.post("/reports/r_deadbeef/match").status_code == 404


def test_cached_matches_on_unknown_report_is_404(client):
    assert client.get("/reports/r_deadbeef/matches").status_code == 404


def test_cached_matches_before_running_the_matcher_is_404(client):
    report_id = post_report(client).json()["report_id"]
    response = client.get(f"/reports/{report_id}/matches")
    assert response.status_code == 404
    assert "match" in response.json()["detail"]


def test_matcher_ranks_the_source_listing_first(client):
    seed_listing("hit", vec=REPORT_VEC)
    for i in range(4):
        seed_listing(f"miss{i}", vec=OTHER_VEC)
    report_id = post_report(client).json()["report_id"]
    body = client.post(f"/reports/{report_id}/match").json()
    assert body["report_id"] == report_id
    assert body["candidates"][0]["listing_id"] == "hit"
    assert body["candidates"][0]["score"] > body["candidates"][1]["score"]


def test_match_response_has_the_spec_candidate_shape(client):
    seed_listing("hit", vec=REPORT_VEC)
    report_id = post_report(client).json()["report_id"]
    candidate = client.post(f"/reports/{report_id}/match").json()["candidates"][0]
    assert set(candidate) == {
        "listing_id",
        "url",
        "score",
        "serial_match",
        "verdict",
        "reasons",
        "suspicion_score",
        "listing_image",
        "report_image",
    }
    assert candidate["url"] == "https://example.invalid/hit"
    assert candidate["suspicion_score"] == pytest.approx(0.2)
    assert candidate["listing_image"] == "data/images/hit/0.jpg"
    assert candidate["report_image"] == f"data/reports/{report_id}/0.jpg"


def test_results_are_capped_at_result_top_k(client):
    for i in range(12):
        seed_listing(f"m{i:02d}", vec=OTHER_VEC)
    report_id = post_report(client).json()["report_id"]
    body = client.post(f"/reports/{report_id}/match").json()
    assert len(body["candidates"]) == RESULT_TOP_K


def test_serial_hit_pins_to_the_front_with_score_one(client):
    # a visually perfect but serial-less listing must still rank below the serial hit
    seed_listing("photo-twin", vec=REPORT_VEC)
    seed_listing("serial-hit", vec=OTHER_VEC, serial_found="GZ0123456")
    report_id = post_report(client, serial="GZO123456").json()["report_id"]
    candidates = client.post(f"/reports/{report_id}/match").json()["candidates"]
    assert candidates[0]["listing_id"] == "serial-hit"
    assert candidates[0]["serial_match"] is True
    assert candidates[0]["score"] == 1.0
    assert candidates[0]["verdict"] == "likely_same"
    assert "Exact serial match" in candidates[0]["reasons"]


def test_cached_matches_mirror_the_live_match_result(client):
    for i in range(6):
        seed_listing(f"m{i}", vec=REPORT_VEC if i == 0 else OTHER_VEC)
    report_id = post_report(client).json()["report_id"]
    live = client.post(f"/reports/{report_id}/match").json()
    cached = client.get(f"/reports/{report_id}/matches").json()
    assert cached["report_id"] == report_id
    assert [c["listing_id"] for c in cached["candidates"]] == [
        c["listing_id"] for c in live["candidates"]
    ]
    assert cached["candidates"][0]["reasons"] == live["candidates"][0]["reasons"]


def test_rerunning_the_matcher_does_not_accumulate_stale_rows(client):
    """A second /match on a changed corpus must not leave more than RESULT_TOP_K cached rows."""
    for i in range(5):
        seed_listing(f"old{i}", vec=OTHER_VEC)
    report_id = post_report(client).json()["report_id"]
    client.post(f"/reports/{report_id}/match")

    conn = db_module.connect()
    conn.execute("DELETE FROM matches WHERE 1=0")  # no-op, keep the connection honest
    conn.close()

    for i in range(5):
        seed_listing(f"new{i}", vec=REPORT_VEC)
    client.post(f"/reports/{report_id}/match")

    cached = client.get(f"/reports/{report_id}/matches").json()["candidates"]
    assert len(cached) <= RESULT_TOP_K


def test_matching_degrades_gracefully_without_listing_vectors(client):
    seed_listing("no-vec")
    report_id = post_report(client).json()["report_id"]
    body = client.post(f"/reports/{report_id}/match").json()
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["score"] >= 0.0


def test_matching_runs_when_the_vlm_is_unavailable(client, monkeypatch):
    import api.routes.reports as reports

    def boom(*args, **kwargs):
        raise RuntimeError("no VLM key")

    monkeypatch.setattr(reports, "extract_attributes", boom)
    seed_listing("hit", vec=REPORT_VEC)
    report_id = post_report(client, brand="Gazelle", color="black").json()["report_id"]
    body = client.post(f"/reports/{report_id}/match").json()
    assert body["candidates"][0]["listing_id"] == "hit"
    assert body["candidates"][0]["verdict"] is None


def test_distance_filter_excludes_far_listings_end_to_end(client):
    seed_listing("near", vec=REPORT_VEC, lat=50.8870, lon=5.9795)  # Heerlen, ~22 km
    seed_listing("far", vec=REPORT_VEC, lat=52.3676, lon=4.9041)  # Amsterdam
    report_id = post_report(client, location="Maastricht").json()["report_id"]
    ids = [c["listing_id"] for c in client.post(f"/reports/{report_id}/match").json()["candidates"]]
    assert ids == ["near"]


def test_suspicion_score_is_passed_through_but_does_not_reorder(client):
    seed_listing("clean", vec=REPORT_VEC, suspicion_score=0.0)
    seed_listing("shady", vec=OTHER_VEC, suspicion_score=1.0)
    report_id = post_report(client).json()["report_id"]
    candidates = client.post(f"/reports/{report_id}/match").json()["candidates"]
    assert candidates[0]["listing_id"] == "clean"
    assert candidates[0]["suspicion_score"] == pytest.approx(0.0)
    assert candidates[1]["suspicion_score"] == pytest.approx(1.0)
