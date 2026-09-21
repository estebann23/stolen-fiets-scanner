"""Report intake and matching routes (matching stays stubbed)."""

from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from api.schemas import MatchCandidate, MatchResponse, ReportCreated
from config import MATCH_RADIUS_KM, REPORTS_DIR, RESULT_TOP_K, ROOT, VERIFY_TOP_K
from db import (
    add_report_image,
    connect,
    fetch_listing,
    fetch_listings_for_matching,
    fetch_matches,
    fetch_report,
    insert_report,
    upsert_match,
)
from enrichment.attributes import BikeAttributes, extract_attributes
from enrichment.embeddings import (
    blob_to_vec,
    embed_description_cached,
    embed_report_images,
)
from matching.explain import explain
from matching.filters import apply_filters
from matching.scorer import score_candidate
from matching.verifier import rerank

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


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _stack_blobs(blobs: list[bytes]):
    import numpy as np

    if not blobs:
        return np.zeros((0, 0), dtype=np.float32)
    return np.stack([blob_to_vec(item) for item in blobs]).astype(np.float32)


def _report_description_from_row(report: dict) -> str:
    return _report_description(report.get("brand"), report.get("color"), report.get("notes"))


def _safe_report_attrs(report: dict, image_paths: list[Path]) -> BikeAttributes | None:
    try:
        return extract_attributes(image_paths, _report_description_from_row(report))
    except Exception as exc:  # noqa: BLE001 — matching still runs on image+text
        log.info("report attributes unavailable %s: %s", report.get("id"), exc)
        try:
            colors = [report["color"]] if report.get("color") else None
            return BikeAttributes(brand=report.get("brand"), colors=colors)
        except Exception:  # noqa: BLE001
            return None


def _candidate_payload(
    report: dict,
    listing: dict,
    *,
    score: float,
    serial_match: bool,
    verdict: str | None,
    reasons: list[str],
) -> MatchCandidate:
    listing_images = listing.get("image_paths") or listing.get("images") or []
    report_images = report.get("images") or []
    return MatchCandidate(
        listing_id=str(listing["id"]),
        url=listing.get("url"),
        score=float(score),
        serial_match=bool(serial_match),
        verdict=verdict,  # type: ignore[arg-type]
        reasons=reasons,
        suspicion_score=listing.get("suspicion_score"),
        listing_image=listing_images[0] if listing_images else None,
        report_image=report_images[0] if report_images else None,
    )


def _run_match_pipeline(report_id: str) -> MatchResponse:
    report = fetch_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")

    conn = connect()
    try:
        image_rows = conn.execute(
            """
            SELECT path, clip_vec FROM report_images
            WHERE report_id = ? ORDER BY id
            """,
            (report_id,),
        ).fetchall()
        report_paths = [_resolve_path(row["path"]) for row in image_rows]
        report_blobs = [bytes(row["clip_vec"]) for row in image_rows if row["clip_vec"]]
        report_vecs = _stack_blobs(report_blobs)
        try:
            report_text = embed_description_cached(
                report_id, _report_description_from_row(report)
            )
        except Exception as exc:  # noqa: BLE001
            log.info("report text vec unavailable: %s", exc)
            report_text = None
        report_attrs = _safe_report_attrs(report, report_paths)
        report["attributes"] = (
            report_attrs.model_dump() if report_attrs is not None else {}
        )
        report["is_electric"] = None if report_attrs is None else report_attrs.is_electric
        report["images"] = [row["path"] for row in image_rows]

        listings = fetch_listings_for_matching(conn)
        kept, serial_hits = apply_filters(report, listings, MATCH_RADIUS_KM)

        scored: list[dict] = []
        for listing in kept:
            listing_id = str(listing["id"])
            try:
                listing_text = embed_description_cached(
                    listing_id, listing.get("description") or ""
                )
            except Exception:  # noqa: BLE001
                listing_text = None
            listing_vecs = _stack_blobs(listing.get("image_blobs") or [])
            serial_hit = listing_id in serial_hits
            score, components = score_candidate(
                report_vecs=report_vecs,
                listing_vecs=listing_vecs,
                report_attrs=report_attrs,
                listing_attrs=listing.get("attributes") or {},
                report_text_vec=report_text,
                listing_text_vec=listing_text,
                serial_hit=serial_hit,
            )
            scored.append(
                {
                    "listing_id": listing_id,
                    "listing": listing,
                    "score": score,
                    "components": components,
                    "serial_match": serial_hit,
                }
            )

        ranked = rerank(report, scored, VERIFY_TOP_K)
        serial_first = [item for item in ranked if item.get("serial_match")]
        others = [item for item in ranked if not item.get("serial_match")]
        top = (serial_first + others)[:RESULT_TOP_K]

        created_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(
            timespec="seconds"
        )
        # Re-running the matcher replaces the cached top-K; stale rows from an
        # earlier corpus must not linger in GET /reports/{id}/matches.
        conn.execute("DELETE FROM matches WHERE report_id = ?", (report_id,))
        candidates: list[MatchCandidate] = []
        for item in top:
            listing = item["listing"]
            verdict_obj = item.get("verdict_obj")
            reasons = explain(
                report,
                listing,
                item.get("components") or {},
                verdict_obj,
                serial_match=bool(item.get("serial_match")),
            )
            upsert_match(
                conn,
                {
                    "report_id": report_id,
                    "listing_id": item["listing_id"],
                    "score": item["score"],
                    "serial_match": int(bool(item.get("serial_match"))),
                    "verdict": item.get("verdict"),
                    "reasons": json.dumps(reasons, ensure_ascii=False),
                    "created_at": created_at,
                },
            )
            candidates.append(
                _candidate_payload(
                    report,
                    listing,
                    score=item["score"],
                    serial_match=bool(item.get("serial_match")),
                    verdict=item.get("verdict"),
                    reasons=reasons,
                )
            )
        conn.commit()
        return MatchResponse(report_id=report_id, candidates=candidates)
    finally:
        conn.close()


@router.post("/reports/{report_id}/match", response_model=MatchResponse)
def run_match(report_id: str) -> MatchResponse:
    return _run_match_pipeline(report_id)


@router.get("/reports/{report_id}/matches", response_model=MatchResponse)
def get_matches(report_id: str) -> MatchResponse:
    report = fetch_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    rows = fetch_matches(report_id)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="run POST /reports/{id}/match first",
        )
    candidates: list[MatchCandidate] = []
    for row in rows:
        listing = fetch_listing(str(row["listing_id"])) or {"id": row["listing_id"]}
        reasons_raw = row.get("reasons")
        reasons: list[str]
        if isinstance(reasons_raw, str):
            try:
                loaded = json.loads(reasons_raw)
                reasons = [str(item) for item in loaded] if isinstance(loaded, list) else [reasons_raw]
            except json.JSONDecodeError:
                reasons = [reasons_raw]
        elif isinstance(reasons_raw, list):
            reasons = [str(item) for item in reasons_raw]
        else:
            reasons = []
        listing["image_paths"] = listing.get("images") or []
        candidates.append(
            _candidate_payload(
                report,
                listing,
                score=float(row["score"] or 0.0),
                serial_match=bool(row["serial_match"]),
                verdict=row.get("verdict"),
                reasons=reasons,
            )
        )
    return MatchResponse(report_id=report_id, candidates=candidates)
