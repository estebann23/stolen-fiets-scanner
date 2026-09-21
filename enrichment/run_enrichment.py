"""Idempotent batch enrichment over the full listing dataset."""

from __future__ import annotations

import argparse
import logging
import time
from typing import Literal

from config import EMB_CACHE_DIR
from db import connect
from enrichment.attributes import enrich_listing
from enrichment.embeddings import embed_description_cached, embed_listing_images
from enrichment.risk_signals import enrich_all_risk
from enrichment.serial_ocr import enrich_listing_serial

log = logging.getLogger(__name__)

StepName = Literal["attributes", "embeddings", "serial", "risk"]


def _listing_ids(limit: int | None) -> list[str]:
    conn = connect()
    try:
        sql = "SELECT id FROM listings ORDER BY id"
        params: tuple[int, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (int(limit),)
        return [str(row["id"]) for row in conn.execute(sql, params)]
    finally:
        conn.close()


def _attr_skip(conn, listing_id: str) -> bool:
    row = conn.execute(
        "SELECT brand FROM listing_attributes WHERE listing_id = ?",
        (listing_id,),
    ).fetchone()
    return bool(row is not None and row["brand"])


def _serial_skip(conn, listing_id: str) -> bool:
    row = conn.execute(
        "SELECT serial_found FROM listing_attributes WHERE listing_id = ?",
        (listing_id,),
    ).fetchone()
    return bool(row is not None and row["serial_found"])


def _emb_skip(conn, listing_id: str) -> bool:
    rows = conn.execute(
        "SELECT clip_vec FROM listing_images WHERE listing_id = ?",
        (listing_id,),
    ).fetchall()
    images_done = bool(rows) and all(row["clip_vec"] is not None for row in rows)
    text_done = (EMB_CACHE_DIR / "text" / f"{listing_id}.npy").is_file()
    return images_done and text_done


def run_batch(
    *,
    force: bool = False,
    limit: int | None = None,
    only: StepName | None = None,
) -> dict[str, dict[str, int]]:
    counts = {
        "attributes": {"done": 0, "skipped": 0, "failed": 0},
        "embeddings": {"done": 0, "skipped": 0, "failed": 0},
        "serial": {"done": 0, "skipped": 0, "failed": 0},
        "risk": {"done": 0, "skipped": 0, "failed": 0},
    }
    want = {only} if only else {"attributes", "embeddings", "serial", "risk"}
    listing_ids = _listing_ids(limit)
    total = len(listing_ids)
    conn = connect()
    try:
        for index, listing_id in enumerate(listing_ids, start=1):
            if "attributes" in want:
                try:
                    if not force and _attr_skip(conn, listing_id):
                        counts["attributes"]["skipped"] += 1
                    else:
                        enrich_listing(conn, listing_id, force=force)
                        counts["attributes"]["done"] += 1
                except Exception as exc:  # noqa: BLE001 — resume the batch
                    counts["attributes"]["failed"] += 1
                    log.info("attributes failed %s: %s", listing_id, exc)

            if "embeddings" in want:
                try:
                    if not force and _emb_skip(conn, listing_id):
                        counts["embeddings"]["skipped"] += 1
                    else:
                        embed_listing_images(conn, listing_id, force=force)
                        listing = conn.execute(
                            "SELECT description FROM listings WHERE id = ?",
                            (listing_id,),
                        ).fetchone()
                        embed_description_cached(
                            listing_id,
                            (listing["description"] if listing else "") or "",
                            force=force,
                        )
                        counts["embeddings"]["done"] += 1
                except Exception as exc:  # noqa: BLE001 — resume the batch
                    counts["embeddings"]["failed"] += 1
                    log.info("embeddings failed %s: %s", listing_id, exc)

            if "serial" in want:
                try:
                    if not force and _serial_skip(conn, listing_id):
                        counts["serial"]["skipped"] += 1
                    else:
                        enrich_listing_serial(conn, listing_id, force=force)
                        counts["serial"]["done"] += 1
                except Exception as exc:  # noqa: BLE001 — resume the batch
                    counts["serial"]["failed"] += 1
                    log.info("serial failed %s: %s", listing_id, exc)

            if index % 25 == 0 or index == total:
                log.info(
                    "progress %s/%s attributes=%s embeddings=%s serial=%s",
                    index,
                    total,
                    counts["attributes"],
                    counts["embeddings"],
                    counts["serial"],
                )

        if "risk" in want:
            try:
                updated = enrich_all_risk(conn)
                counts["risk"]["done"] = updated
            except Exception as exc:  # noqa: BLE001 — resume the batch
                counts["risk"]["failed"] += 1
                log.info("risk failed: %s", exc)
    finally:
        conn.close()
    return counts


def _print_summary(counts: dict[str, dict[str, int]], elapsed_s: float) -> None:
    print(f"{'step':<12} {'done':>6} {'skipped':>8} {'failed':>7}")
    for step in ("attributes", "embeddings", "serial", "risk"):
        row = counts[step]
        print(
            f"{step:<12} {row['done']:6d} {row['skipped']:8d} {row['failed']:7d}"
        )
    print(f"wall-clock {elapsed_s:.1f}s")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Batch-enrich stolen-bike listings.")
    parser.add_argument("--force", action="store_true", help="re-do even if present")
    parser.add_argument("--limit", type=int, default=None, help="first N listings")
    parser.add_argument(
        "--only",
        choices=("attributes", "embeddings", "serial", "risk"),
        default=None,
        help="run a single step",
    )
    args = parser.parse_args()
    started = time.perf_counter()
    counts = run_batch(force=args.force, limit=args.limit, only=args.only)
    _print_summary(counts, time.perf_counter() - started)


if __name__ == "__main__":
    main()
