"""SQLite schema init and listing import (SPEC §6)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from config import DB_PATH, RAW_LISTINGS_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS listings (
  id TEXT PRIMARY KEY,
  title TEXT,
  description TEXT,
  price REAL,
  location TEXT,
  lat REAL,
  lon REAL,
  posted_at TIMESTAMP,
  seller_id TEXT,
  url TEXT,
  suspicion_score REAL
);

CREATE TABLE IF NOT EXISTS listing_images (
  id INTEGER PRIMARY KEY,
  listing_id TEXT REFERENCES listings(id),
  path TEXT,
  clip_vec BLOB
);

CREATE TABLE IF NOT EXISTS listing_attributes (
  listing_id TEXT PRIMARY KEY REFERENCES listings(id),
  brand TEXT,
  model TEXT,
  bike_type TEXT,
  colors JSON,
  frame_shape TEXT,
  wheel_size TEXT,
  is_electric BOOLEAN,
  accessories JSON,
  marks JSON,
  serial_found TEXT
);

CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  created_at TIMESTAMP,
  stolen_at TIMESTAMP,
  stolen_lat REAL,
  stolen_lon REAL,
  serial TEXT,
  brand TEXT,
  color TEXT,
  notes TEXT,
  police_report_nr TEXT
);

CREATE TABLE IF NOT EXISTS report_images (
  id INTEGER PRIMARY KEY,
  report_id TEXT REFERENCES reports(id),
  path TEXT,
  clip_vec BLOB
);

CREATE TABLE IF NOT EXISTS matches (
  report_id TEXT REFERENCES reports(id),
  listing_id TEXT REFERENCES listings(id),
  score REAL,
  serial_match BOOLEAN,
  verdict TEXT,
  reasons JSON,
  created_at TIMESTAMP,
  PRIMARY KEY (report_id, listing_id)
);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection | None = None) -> None:
    own = conn is None
    conn = conn or connect()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        if own:
            conn.close()


def _parse_posted_at(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


def upsert_listing(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO listings (
          id, title, description, price, location, lat, lon,
          posted_at, seller_id, url, suspicion_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          title=excluded.title,
          description=excluded.description,
          price=excluded.price,
          location=excluded.location,
          lat=excluded.lat,
          lon=excluded.lon,
          posted_at=excluded.posted_at,
          seller_id=excluded.seller_id,
          url=excluded.url,
          suspicion_score=excluded.suspicion_score
        """,
        (
            row["id"],
            row.get("title"),
            row.get("description"),
            row.get("price"),
            row.get("location"),
            row.get("lat"),
            row.get("lon"),
            _parse_posted_at(row.get("posted_at")),
            row.get("seller_id"),
            row.get("url"),
            row.get("suspicion_score"),
        ),
    )
    conn.execute("DELETE FROM listing_images WHERE listing_id = ?", (row["id"],))
    for path in row.get("image_paths") or []:
        conn.execute(
            "INSERT INTO listing_images (listing_id, path) VALUES (?, ?)",
            (row["id"], path),
        )


def replace_listings_from_jsonl(jsonl_path: Path | None = None) -> int:
    """Drop existing listing rows, then import JSONL (one-time scrape replace)."""
    path = jsonl_path or RAW_LISTINGS_PATH
    conn = connect()
    try:
        init_schema(conn)
        conn.execute("DELETE FROM matches")
        conn.execute("DELETE FROM listing_images")
        conn.execute("DELETE FROM listing_attributes")
        conn.execute("DELETE FROM listings")
        conn.commit()
        return import_listings_jsonl(path, conn)
    finally:
        conn.close()


def import_listings_jsonl(
    jsonl_path: Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    path = jsonl_path or RAW_LISTINGS_PATH
    own = conn is None
    conn = conn or connect()
    count = 0
    try:
        init_schema(conn)
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                upsert_listing(conn, json.loads(line))
                count += 1
        conn.commit()
        return count
    finally:
        if own:
            conn.close()


def fetch_listing(listing_id: str) -> dict[str, Any] | None:
    conn = connect()
    try:
        listing = conn.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
        if listing is None:
            return None
        images = conn.execute(
            "SELECT path FROM listing_images WHERE listing_id = ? ORDER BY id",
            (listing_id,),
        ).fetchall()
        attrs = conn.execute(
            "SELECT * FROM listing_attributes WHERE listing_id = ?",
            (listing_id,),
        ).fetchone()
        payload = dict(listing)
        payload["images"] = [row["path"] for row in images]
        payload["attributes"] = _attributes_dict(attrs)
        return payload
    finally:
        conn.close()


def _attributes_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)

    def _load(key: str) -> Any:
        raw = data.get(key)
        if raw in (None, ""):
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
        return raw

    data["colors"] = _load("colors")
    data["accessories"] = _load("accessories")
    data["marks"] = _load("marks")
    return data


def listing_count() -> int:
    conn = connect()
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM listings").fetchone()
        return int(row["n"]) if row else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def iter_listing_ids(conn: sqlite3.Connection) -> Iterable[str]:
    for row in conn.execute("SELECT id FROM listings"):
        yield row["id"]


def insert_report(conn: sqlite3.Connection, report: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO reports (
          id, created_at, stolen_at, stolen_lat, stolen_lon,
          serial, brand, color, notes, police_report_nr
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report["id"],
            report.get("created_at"),
            report.get("stolen_at"),
            report.get("stolen_lat"),
            report.get("stolen_lon"),
            report.get("serial"),
            report.get("brand"),
            report.get("color"),
            report.get("notes"),
            report.get("police_report_nr"),
        ),
    )


def add_report_image(conn: sqlite3.Connection, report_id: str, path: str) -> int:
    cursor = conn.execute(
        "INSERT INTO report_images (report_id, path) VALUES (?, ?)",
        (report_id, path),
    )
    return int(cursor.lastrowid)


def fetch_report(report_id: str) -> dict[str, Any] | None:
    conn = connect()
    try:
        report = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        if report is None:
            return None
        images = conn.execute(
            "SELECT path FROM report_images WHERE report_id = ? ORDER BY id",
            (report_id,),
        ).fetchall()
        payload = dict(report)
        payload["images"] = [row["path"] for row in images]
        return payload
    finally:
        conn.close()


def upsert_match(conn: sqlite3.Connection, match: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO matches (
          report_id, listing_id, score, serial_match, verdict, reasons, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            match["report_id"],
            match["listing_id"],
            match.get("score"),
            match.get("serial_match"),
            match.get("verdict"),
            match.get("reasons"),
            match.get("created_at"),
        ),
    )


def fetch_matches(report_id: str) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM matches
            WHERE report_id = ?
            ORDER BY serial_match DESC,
              CASE verdict
                WHEN 'likely_same' THEN 0
                WHEN 'possibly_same' THEN 1
                WHEN 'different' THEN 3
                ELSE 2
              END,
              score DESC,
              listing_id ASC
            """,
            (report_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def fetch_listings_for_matching(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Listing rows joined with attributes, photo paths, and clip blobs."""
    attr_rows = {
        row["listing_id"]: _attributes_dict(row)
        for row in conn.execute("SELECT * FROM listing_attributes")
    }
    image_paths: dict[str, list[str]] = {}
    image_blobs: dict[str, list[bytes]] = {}
    for row in conn.execute(
        "SELECT listing_id, path, clip_vec FROM listing_images ORDER BY id"
    ):
        listing_id = str(row["listing_id"])
        image_paths.setdefault(listing_id, []).append(str(row["path"]))
        blob = row["clip_vec"]
        if blob:
            image_blobs.setdefault(listing_id, []).append(bytes(blob))
    listings: list[dict[str, Any]] = []
    for row in conn.execute("SELECT * FROM listings"):
        listing_id = str(row["id"])
        attrs = attr_rows.get(listing_id) or {}
        payload = dict(row)
        payload["attributes"] = attrs
        payload["serial_found"] = attrs.get("serial_found")
        payload["is_electric"] = attrs.get("is_electric")
        payload["image_paths"] = image_paths.get(listing_id, [])
        payload["image_blobs"] = image_blobs.get(listing_id, [])
        listings.append(payload)
    return listings


def main() -> None:
    init_schema()
    imported = 0
    if RAW_LISTINGS_PATH.exists() and RAW_LISTINGS_PATH.stat().st_size > 0:
        imported = import_listings_jsonl()
    print(f"schema ready at {DB_PATH} ({imported} listings imported)")


if __name__ == "__main__":
    main()
