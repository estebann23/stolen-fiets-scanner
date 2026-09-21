"""Report intake and matching routes (matching stays stubbed)."""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from api.schemas import MatchResponse, ReportCreated
from config import REPORTS_DIR, ROOT
from db import add_report_image, connect, insert_report
from enrichment.attributes import extract_attributes
from enrichment.embeddings import embed_description_cached, embed_report_images

log = logging.getLogger(__name__)

router = APIRouter()

# Hackathon stand-in for a real geocoder (kept offline on purpose).
GAZETTEER: dict[str, tuple[float, float]] = {
    "maastricht": (50.8483, 5.6886),
    "valkenburg": (50.8658, 5.8322),
    "meerssen": (50.8892, 5.7382),
    "heerlen": (50.8870, 5.9795),
    "sittard": (51.0000, 5.8667),
    "roermond": (51.1942, 5.9870),
    "genk": (50.9650, 5.5000),
    "hasselt": (50.9307, 5.3374),
    "liège": (50.6333, 5.5667),
    "liege": (50.6333, 5.5667),
    "aachen": (50.7753, 6.0839),
    "tongeren": (50.7806, 5.4647),
    "bilzen": (50.8736, 5.5189),
}

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/x-png",
}


def _resolve_coords(
    location: str | None,
    stolen_lat: float | None,
    stolen_lon: float | None,
) -> tuple[float | None, float | None]:
    if stolen_lat is not None and stolen_lon is not None:
        return stolen_lat, stolen_lon
    if location:
        coords = GAZETTEER.get(location.strip().casefold())
        if coords is not None:
            return coords
    return None, None


def _parse_stolen_at(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="stolen_at is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="stolen_at must be an ISO date or datetime",
        ) from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.isoformat(timespec="seconds")


def _is_allowed_photo(upload: UploadFile) -> bool:
    name = upload.filename or ""
    suffix = Path(name).suffix.lower()
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if suffix in ALLOWED_SUFFIXES:
        return True
    if content_type in ALLOWED_CONTENT_TYPES:
        return True
    return False


def _save_report_jpegs(report_id: str, uploads: list[UploadFile]) -> list[Path]:
    dest_dir = REPORTS_DIR / report_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for index, upload in enumerate(uploads):
        raw = upload.file.read()
        try:
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:  # noqa: BLE001 — reject unreadable uploads
            raise HTTPException(
                status_code=422,
                detail=f"could not read photo {index} as an image",
            ) from exc
        dest = dest_dir / f"{index}.jpg"
        image.save(dest, format="JPEG", quality=90)
        saved.append(dest)
    return saved


def _report_description(
    brand: str | None,
    color: str | None,
    notes: str | None,
) -> str:
    return " ".join(part.strip() for part in (brand, color, notes) if part and part.strip())


@router.post("/reports", response_model=ReportCreated, status_code=201)
def create_report(
    photos: list[UploadFile] = File(...),
    stolen_at: str = Form(...),
    location: str | None = Form(None),
    stolen_lat: float | None = Form(None),
    stolen_lon: float | None = Form(None),
    serial: str | None = Form(None),
    brand: str | None = Form(None),
    color: str | None = Form(None),
    police_report_nr: str | None = Form(None),
    notes: str | None = Form(None),
) -> ReportCreated:
    if not photos:
        raise HTTPException(status_code=422, detail="provide between 1 and 5 photos")
    if len(photos) > 5:
        raise HTTPException(status_code=422, detail="provide between 1 and 5 photos")
    for upload in photos:
        if not _is_allowed_photo(upload):
            raise HTTPException(
                status_code=422,
                detail="photos must be jpg, jpeg, png, or webp",
            )

    report_id = f"r_{uuid4().hex[:8]}"
    lat, lon = _resolve_coords(location, stolen_lat, stolen_lon)
    stolen_at_iso = _parse_stolen_at(stolen_at)
    created_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")

    saved = _save_report_jpegs(report_id, photos)
    relative_paths = [
        path.resolve().relative_to(ROOT).as_posix() for path in saved
    ]

    conn = connect()
    try:
        insert_report(
            conn,
            {
                "id": report_id,
                "created_at": created_at,
                "stolen_at": stolen_at_iso,
                "stolen_lat": lat,
                "stolen_lon": lon,
                "serial": serial,
                "brand": brand,
                "color": color,
                "notes": notes,
                "police_report_nr": police_report_nr,
            },
        )
        for rel in relative_paths:
            add_report_image(conn, report_id, rel)
        conn.commit()
        embed_report_images(conn, report_id)
        embed_description_cached(report_id, _report_description(brand, color, notes))
        try:
            attrs = extract_attributes(saved, _report_description(brand, color, notes))
            log.info(
                "report attributes %s confidence=%s",
                report_id,
                attrs.confidence,
            )
        except Exception as exc:  # noqa: BLE001 — embeddings already persisted
            log.info("report attributes skipped %s: %s", report_id, exc)
    finally:
        conn.close()

    return ReportCreated(report_id=report_id)


@router.post("/reports/{report_id}/match", response_model=MatchResponse)
def run_match(report_id: str) -> MatchResponse:
    raise HTTPException(status_code=501, detail="matching not implemented yet")


@router.get("/reports/{report_id}/matches", response_model=MatchResponse)
def get_matches(report_id: str) -> MatchResponse:
    raise HTTPException(status_code=501, detail="matching not implemented yet")
