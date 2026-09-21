"""VLM → structured bike attributes (strict JSON, Pydantic-validated). SPEC §5.2."""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError, field_validator

from config import ROOT
from db import connect
from enrichment.llm_client import SETUP_HINT, call_vlm_json, vlm_ready

log = logging.getLogger(__name__)

BikeType = Literal["city", "e-bike", "race", "mtb", "cargo", "hybrid", "other"]
FrameShape = Literal["low-step", "diamond", "mixte", "unknown"]

BIKE_TYPES: frozenset[str] = frozenset(
    {"city", "e-bike", "race", "mtb", "cargo", "hybrid", "other"}
)
FRAME_SHAPES: frozenset[str] = frozenset({"low-step", "diamond", "mixte", "unknown"})

SYSTEM_PROMPT = """You extract bicycle attributes from listing photos and a seller description.
Reply with STRICT JSON only — a single object matching this schema, no markdown, no extra keys:
{
  "brand": string or null,
  "model": string or null,
  "bike_type": "city" | "e-bike" | "race" | "mtb" | "cargo" | "hybrid" | "other" | null,
  "colors": [string] or null,
  "frame_shape": "low-step" | "diamond" | "mixte" | "unknown",
  "wheel_size": string or null,
  "is_electric": boolean or null,
  "accessories": [string] or null,
  "marks": [string] or null,
  "confidence": number 0-1
}
Allowed bike_type values: city, e-bike, race, mtb, cargo, hybrid, other.
Allowed frame_shape values: low-step, diamond, mixte, unknown.
The description may be Dutch. Normalise colours to canonical English
(black, grey, blue, green, white, red, silver, anthracite, and similar).
If unsure, use null (or "unknown" for frame_shape). Set confidence between 0 and 1.
"""


class BikeAttributes(BaseModel):
    brand: str | None = None
    model: str | None = None
    bike_type: BikeType | None = None
    colors: list[str] | None = None
    frame_shape: FrameShape | None = None
    wheel_size: str | None = None
    is_electric: bool | None = None
    accessories: list[str] | None = None
    marks: list[str] | None = None
    confidence: float | None = None

    @field_validator("bike_type", mode="before")
    @classmethod
    def _coerce_bike_type(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        text = str(value).strip().lower()
        if text in BIKE_TYPES:
            return text
        return None

    @field_validator("frame_shape", mode="before")
    @classmethod
    def _coerce_frame_shape(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        text = str(value).strip().lower()
        if text in FRAME_SHAPES:
            return text
        return "unknown"

    @field_validator("colors", "accessories", "marks", mode="before")
    @classmethod
    def _coerce_str_list(cls, value: Any) -> list[str] | None:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value]
        return None

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, min(1.0, number))


def _null_attributes() -> BikeAttributes:
    return BikeAttributes(confidence=0.0)


def extract_attributes(image_paths: list[Path], description: str) -> BikeAttributes:
    """Shared by listings and reports: photos + text → validated attributes."""
    user_text = (
        "Extract bike attributes from the photos and this description.\n\n"
        f"{description or ''}"
    )
    parsed = call_vlm_json(SYSTEM_PROMPT, user_text, image_paths)
    if parsed is None:
        return _null_attributes()
    try:
        return BikeAttributes.model_validate(parsed)
    except ValidationError:
        return _null_attributes()


def _json_or_none(value: list[str] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def store_attributes(
    conn: sqlite3.Connection,
    listing_id: str,
    attrs: BikeAttributes,
) -> None:
    """Upsert listing_attributes columns; never overwrite serial_found."""
    conn.execute(
        """
        INSERT INTO listing_attributes (
          listing_id, brand, model, bike_type, colors, frame_shape,
          wheel_size, is_electric, accessories, marks
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(listing_id) DO UPDATE SET
          brand=excluded.brand,
          model=excluded.model,
          bike_type=excluded.bike_type,
          colors=excluded.colors,
          frame_shape=excluded.frame_shape,
          wheel_size=excluded.wheel_size,
          is_electric=excluded.is_electric,
          accessories=excluded.accessories,
          marks=excluded.marks
        """,
        (
            listing_id,
            attrs.brand,
            attrs.model,
            attrs.bike_type,
            _json_or_none(attrs.colors),
            attrs.frame_shape,
            attrs.wheel_size,
            attrs.is_electric,
            _json_or_none(attrs.accessories),
            _json_or_none(attrs.marks),
        ),
    )
    conn.commit()


def _row_to_attributes(row: sqlite3.Row) -> BikeAttributes:
    def _load_list(raw: Any) -> list[str] | None:
        if raw in (None, ""):
            return None
        if isinstance(raw, list):
            return [str(item) for item in raw]
        if isinstance(raw, str):
            try:
                loaded = json.loads(raw)
            except json.JSONDecodeError:
                return [raw]
            if isinstance(loaded, list):
                return [str(item) for item in loaded]
        return None

    electric = row["is_electric"]
    is_electric: bool | None
    if electric is None:
        is_electric = None
    else:
        is_electric = bool(electric)

    return BikeAttributes(
        brand=row["brand"],
        model=row["model"],
        bike_type=row["bike_type"],
        colors=_load_list(row["colors"]),
        frame_shape=row["frame_shape"],
        wheel_size=row["wheel_size"],
        is_electric=is_electric,
        accessories=_load_list(row["accessories"]),
        marks=_load_list(row["marks"]),
        confidence=None,
    )


def _resolve_image_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def enrich_listing(
    conn: sqlite3.Connection,
    listing_id: str,
    *,
    force: bool = False,
) -> BikeAttributes:
    """Idempotent: skip the API if a non-null brand is already stored (unless force)."""
    existing = conn.execute(
        "SELECT * FROM listing_attributes WHERE listing_id = ?",
        (listing_id,),
    ).fetchone()
    if existing is not None and existing["brand"] and not force:
        log.info("skip %s", listing_id)
        return _row_to_attributes(existing)

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

    attrs = extract_attributes(image_paths, listing["description"] or "")
    store_attributes(conn, listing_id, attrs)
    log.info("done %s", listing_id)
    return attrs


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not vlm_ready():
        print(SETUP_HINT)
        sys.exit(0)
    conn = connect()
    try:
        row = conn.execute("SELECT id FROM listings LIMIT 1").fetchone()
        if row is None:
            print("No listings in the database.")
            sys.exit(0)
        attrs = enrich_listing(conn, row["id"])
        print(attrs.model_dump_json(indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
