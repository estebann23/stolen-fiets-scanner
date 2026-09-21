"""Extract serial numbers from listing photos and description text."""

from __future__ import annotations

import logging
import re
import sqlite3
import sys
from pathlib import Path

from config import ROOT
from db import connect
from enrichment.llm_client import SETUP_HINT, call_vlm_json, vlm_ready

log = logging.getLogger(__name__)

SERIAL_OCR_PROMPT = """You read bicycle frame / serial numbers from photos.
Reply with STRICT JSON only — a single object, no markdown, no extra keys:
{"serial": string or null}
If no frame or serial number is clearly visible, set serial to null. Do not invent.
"""

_SERIAL_KEYWORD_RE = re.compile(
    r"(?i)(?:framenummer|frame\s+nummer|frame\s+nr\.?|framenr|serienummer|"
    r"frame\s+number|\bserial\b)\s*[:#=\-]?\s*"
    r"([A-Za-z0-9][A-Za-z0-9\-\s]{4,30})"
)


def _resolve_image_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def normalise_serial(s: str) -> str:
    """Uppercase; keep only A–Z and 0–9 (strip spaces, dashes, punctuation)."""
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def extract_serial_from_text(description: str) -> str | None:
    """Keyword-anchored frame/serial token from Dutch/English listing text."""
    if not description:
        return None
    for match in _SERIAL_KEYWORD_RE.finditer(description):
        normalised = normalise_serial(match.group(1))
        if 6 <= len(normalised) <= 20:
            return normalised
    return None


def extract_serial_from_images(image_paths: list[Path]) -> str | None:
    """VLM OCR for a visible frame number; uses llm_client disk cache."""
    if not image_paths:
        return None
    parsed = call_vlm_json(
        SERIAL_OCR_PROMPT,
        "Read any frame or serial number visible in these photos.",
        image_paths,
    )
    if not isinstance(parsed, dict):
        return None
    raw = parsed.get("serial")
    if raw is None or raw == "":
        return None
    normalised = normalise_serial(str(raw))
    if 6 <= len(normalised) <= 20:
        return normalised
    return None


def extract_serial(image_paths: list[Path], description: str) -> str | None:
    """Text first, then photos. Shared by listings and reports."""
    from_text = extract_serial_from_text(description)
    if from_text:
        return from_text
    return extract_serial_from_images(image_paths)


def enrich_listing_serial(
    conn: sqlite3.Connection,
    listing_id: str,
    *,
    force: bool = False,
) -> str | None:
    """Write listing_attributes.serial_found only; never clobber other columns."""
    existing = conn.execute(
        "SELECT serial_found FROM listing_attributes WHERE listing_id = ?",
        (listing_id,),
    ).fetchone()
    if existing is not None and existing["serial_found"] and not force:
        log.info("skip %s", listing_id)
        return str(existing["serial_found"])

    listing = conn.execute(
        "SELECT description FROM listings WHERE id = ?",
        (listing_id,),
    ).fetchone()
    if listing is None:
        raise ValueError(f"listing not found: {listing_id}")

    image_rows = conn.execute(
        "SELECT path FROM listing_images WHERE listing_id = ? ORDER BY id",
        (listing_id,),
    ).fetchall()
    image_paths = [_resolve_image_path(row["path"]) for row in image_rows]
    image_paths = [path for path in image_paths if path.is_file()]

    serial = extract_serial(image_paths, listing["description"] or "")
    conn.execute(
        """
        INSERT INTO listing_attributes (listing_id, serial_found)
        VALUES (?, ?)
        ON CONFLICT(listing_id) DO UPDATE SET
          serial_found = excluded.serial_found
        """,
        (listing_id, serial),
    )
    conn.commit()
    log.info("done %s", listing_id)
    return serial


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(normalise_serial("gz 1234-5678"))
    print(extract_serial_from_text("Framenummer GZ12345678."))
    print(extract_serial_from_text("Nette stadsfiets, weinig gebruikt."))
    if not vlm_ready():
        print(SETUP_HINT)
        sys.exit(0)
    conn = connect()
    try:
        row = conn.execute("SELECT id FROM listings ORDER BY id LIMIT 1").fetchone()
        if row is None:
            print("No listings in the database.")
            return
        print(enrich_listing_serial(conn, row["id"]))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
