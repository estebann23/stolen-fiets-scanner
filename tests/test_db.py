"""SPEC 6: schema, listing import, report helpers, match persistence and ordering."""

from __future__ import annotations

import json

import db as db_module
from db import (
    add_report_image,
    fetch_listing,
    fetch_listings_for_matching,
    fetch_matches,
    fetch_report,
    import_listings_jsonl,
    insert_report,
    listing_count,
    replace_listings_from_jsonl,
    upsert_listing,
    upsert_match,
)

EXPECTED_TABLES = {
    "listings",
    "listing_images",
    "listing_attributes",
    "reports",
    "report_images",
    "matches",
}


def test_schema_creates_every_spec_table(conn):
    names = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert EXPECTED_TABLES <= names


def test_reports_table_has_no_location_column(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(reports)")}
    assert "location" not in cols
    assert {"stolen_lat", "stolen_lon"} <= cols


def test_init_schema_is_idempotent(conn):
    db_module.init_schema(conn)
    db_module.init_schema(conn)


def test_upsert_listing_replaces_images_rather_than_appending(conn):
    row = {"id": "l1", "title": "Gazelle", "image_paths": ["data/images/l1/0.jpg"]}
    upsert_listing(conn, row)
    upsert_listing(conn, {**row, "image_paths": ["data/images/l1/0.jpg", "data/images/l1/1.jpg"]})
    conn.commit()
    paths = [r[0] for r in conn.execute("SELECT path FROM listing_images WHERE listing_id='l1'")]
    assert paths == ["data/images/l1/0.jpg", "data/images/l1/1.jpg"]


def test_import_listings_jsonl_counts_rows(tmp_db, tmp_path):
    jsonl = tmp_path / "listings.jsonl"
    jsonl.write_text(
        "\n".join(
            json.dumps({"id": f"m{i}", "title": f"bike {i}", "image_paths": [f"data/images/m{i}/0.jpg"]})
            for i in range(3)
        )
        + "\n\n",  # trailing blank line must be tolerated
        encoding="utf-8",
    )
    assert import_listings_jsonl(jsonl) == 3
    assert listing_count() == 3


def test_replace_listings_wipes_old_corpus_and_matches(tmp_db, tmp_path):
    first = tmp_path / "a.jsonl"
    first.write_text(json.dumps({"id": "old", "title": "old"}) + "\n", encoding="utf-8")
    replace_listings_from_jsonl(first)

    conn = db_module.connect()
    insert_report(conn, {"id": "r_1", "stolen_at": "2026-01-01T00:00:00"})
    upsert_match(conn, {"report_id": "r_1", "listing_id": "old", "score": 0.5})
    conn.commit()
    conn.close()

    second = tmp_path / "b.jsonl"
    second.write_text(json.dumps({"id": "new", "title": "new"}) + "\n", encoding="utf-8")
    assert replace_listings_from_jsonl(second) == 1
    assert fetch_listing("old") is None
    assert fetch_listing("new") is not None
    assert fetch_matches("r_1") == []
    # reports survive a corpus refresh
    assert fetch_report("r_1") is not None


def test_fetch_listing_decodes_json_attribute_columns(conn, tmp_db):
    upsert_listing(conn, {"id": "l1", "title": "Gazelle", "image_paths": ["data/images/l1/0.jpg"]})
    conn.execute(
        "INSERT INTO listing_attributes (listing_id, brand, colors, accessories, marks)"
        " VALUES ('l1', 'Gazelle', ?, ?, ?)",
        (json.dumps(["black"]), json.dumps(["rear rack"]), json.dumps(["scratch"])),
    )
    conn.commit()
    row = fetch_listing("l1")
    assert row["attributes"]["colors"] == ["black"]
    assert row["attributes"]["accessories"] == ["rear rack"]
    assert row["attributes"]["marks"] == ["scratch"]
    assert row["images"] == ["data/images/l1/0.jpg"]


def test_fetch_listing_unknown_id_is_none(tmp_db):
    assert fetch_listing("nope") is None


def test_report_roundtrip(conn, tmp_db):
    insert_report(
        conn,
        {
            "id": "r_abc12345",
            "created_at": "2026-09-01T10:00:00",
            "stolen_at": "2026-08-30T00:00:00",
            "stolen_lat": 50.8483,
            "stolen_lon": 5.6886,
            "serial": "GZ123456",
            "brand": "Gazelle",
            "color": "black",
            "notes": "rear rack",
            "police_report_nr": "PL-1",
        },
    )
    add_report_image(conn, "r_abc12345", "data/reports/r_abc12345/0.jpg")
    add_report_image(conn, "r_abc12345", "data/reports/r_abc12345/1.jpg")
    conn.commit()
    row = fetch_report("r_abc12345")
    assert row["serial"] == "GZ123456"
    assert row["images"] == [
        "data/reports/r_abc12345/0.jpg",
        "data/reports/r_abc12345/1.jpg",
    ]


def test_fetch_matches_orders_serial_then_verdict_then_score(conn, tmp_db):
    insert_report(conn, {"id": "r_1", "stolen_at": "2026-01-01T00:00:00"})
    for listing_id in ("a", "b", "c", "d", "e"):
        upsert_listing(conn, {"id": listing_id})
    rows = [
        ("a", 0.10, 0, "different"),
        ("b", 0.20, 0, None),
        ("c", 0.30, 0, "possibly_same"),
        ("d", 0.40, 0, "likely_same"),
        ("e", 0.05, 1, "likely_same"),
    ]
    for listing_id, score, serial_match, verdict in rows:
        upsert_match(
            conn,
            {
                "report_id": "r_1",
                "listing_id": listing_id,
                "score": score,
                "serial_match": serial_match,
                "verdict": verdict,
                "reasons": json.dumps([]),
                "created_at": "2026-01-02T00:00:00",
            },
        )
    conn.commit()
    order = [row["listing_id"] for row in fetch_matches("r_1")]
    assert order == ["e", "d", "c", "b", "a"]


def test_upsert_match_is_idempotent_on_the_same_pair(conn, tmp_db):
    insert_report(conn, {"id": "r_1", "stolen_at": "2026-01-01T00:00:00"})
    upsert_listing(conn, {"id": "l1"})
    for score in (0.1, 0.9):
        upsert_match(conn, {"report_id": "r_1", "listing_id": "l1", "score": score})
    conn.commit()
    rows = fetch_matches("r_1")
    assert len(rows) == 1
    assert rows[0]["score"] == 0.9


def test_fetch_listings_for_matching_joins_attributes_images_and_blobs(conn, tmp_db):
    upsert_listing(conn, {"id": "l1", "image_paths": ["data/images/l1/0.jpg", "data/images/l1/1.jpg"]})
    conn.execute(
        "INSERT INTO listing_attributes (listing_id, brand, is_electric, serial_found)"
        " VALUES ('l1', 'Gazelle', 1, 'GZ123456')"
    )
    conn.execute(
        "UPDATE listing_images SET clip_vec = ? WHERE listing_id='l1' AND path='data/images/l1/0.jpg'",
        (b"\x00\x00\x80\x3f",),
    )
    conn.commit()
    rows = fetch_listings_for_matching(conn)
    assert len(rows) == 1
    row = rows[0]
    assert row["serial_found"] == "GZ123456"
    assert row["is_electric"] == 1
    assert row["image_paths"] == ["data/images/l1/0.jpg", "data/images/l1/1.jpg"]
    assert len(row["image_blobs"]) == 1  # only embedded photos contribute vectors


def test_listing_count_on_empty_db(tmp_db):
    assert listing_count() == 0
