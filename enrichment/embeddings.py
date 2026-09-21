"""CLIP image + text embeddings (normalised for cosine similarity)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from config import CLIP_MODEL, CLIP_PRETRAINED, EMB_CACHE_DIR, ROOT
from db import connect

log = logging.getLogger(__name__)

# Lazy singleton. First run downloads the model weights (~350MB for ViT-B-32).
_model: Any = None
_preprocess: Any = None
_tokenizer: Any = None
_device: str | None = None


def _resolve_image_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    out = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(out))
    if norm == 0.0:
        return out
    return (out / norm).astype(np.float32)


def _clip() -> tuple[Any, Any, Any, str]:
    """Load open_clip once: model, preprocess, tokenizer, device."""
    global _model, _preprocess, _tokenizer, _device
    if _model is not None and _preprocess is not None and _tokenizer is not None:
        assert _device is not None
        return _model, _preprocess, _tokenizer, _device

    import torch
    import open_clip

    device = "cuda" if torch.cuda.is_available() else "cpu"
    # First run downloads the model weights (~350MB for ViT-B-32).
    model, _, preprocess = open_clip.create_model_and_transforms(
        CLIP_MODEL,
        pretrained=CLIP_PRETRAINED,
        device=device,
    )
    model.eval()
    tokenizer = open_clip.get_tokenizer(CLIP_MODEL)
    _model, _preprocess, _tokenizer, _device = model, preprocess, tokenizer, device
    log.info("loaded clip model=%s pretrained=%s device=%s", CLIP_MODEL, CLIP_PRETRAINED, device)
    return _model, _preprocess, _tokenizer, _device


def embed_image(path: Path) -> np.ndarray:
    """Open with PIL, preprocess, encode, L2-norm → float32 shape (D,)."""
    import torch

    model, preprocess, _, device = _clip()
    image = Image.open(path).convert("RGB")
    tensor = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        features = model.encode_image(tensor)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.squeeze(0).detach().cpu().numpy().astype(np.float32)


def embed_text(text: str) -> np.ndarray:
    """open_clip tokenizer + encode_text, L2-norm → float32 shape (D,)."""
    import torch

    model, _, tokenizer, device = _clip()
    tokens = tokenizer([text or " "]).to(device)
    with torch.no_grad():
        features = model.encode_text(tokens)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.squeeze(0).detach().cpu().numpy().astype(np.float32)


def vec_to_blob(v: np.ndarray) -> bytes:
    return np.asarray(v, dtype=np.float32).tobytes()


def blob_to_vec(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32).copy()


def embed_listing_images(
    conn: sqlite3.Connection,
    listing_id: str,
    *,
    force: bool = False,
) -> int:
    """Embed listing photos into listing_images.clip_vec. Idempotent unless force."""
    return _embed_entity_images(
        conn,
        table="listing_images",
        fk_column="listing_id",
        entity_id=listing_id,
        force=force,
    )


def embed_report_images(
    conn: sqlite3.Connection,
    report_id: str,
    *,
    force: bool = False,
) -> int:
    """Same encoder path as listings, writing report_images.clip_vec."""
    return _embed_entity_images(
        conn,
        table="report_images",
        fk_column="report_id",
        entity_id=report_id,
        force=force,
    )


def _embed_entity_images(
    conn: sqlite3.Connection,
    *,
    table: str,
    fk_column: str,
    entity_id: str,
    force: bool,
) -> int:
    if table not in {"listing_images", "report_images"} or fk_column not in {
        "listing_id",
        "report_id",
    }:
        raise ValueError("unsupported image table")
    rows = conn.execute(
        f"SELECT id, path, clip_vec FROM {table} WHERE {fk_column} = ? ORDER BY id",
        (entity_id,),
    ).fetchall()
    total = len(rows)
    pending = [row for row in rows if force or row["clip_vec"] is None]
    if not pending:
        log.info("skip %s: 0/%s", entity_id, total)
        return 0

    written = 0
    for row in pending:
        path = _resolve_image_path(row["path"])
        if not path.is_file():
            log.info("missing image %s %s", entity_id, path)
            continue
        blob = vec_to_blob(embed_image(path))
        conn.execute(
            f"UPDATE {table} SET clip_vec = ? WHERE id = ?",
            (blob, row["id"]),
        )
        written += 1
    conn.commit()
    log.info("done %s: %s/%s", entity_id, written, total)
    return written


def embed_description_cached(
    entity_id: str,
    text: str,
    *,
    force: bool = False,
) -> np.ndarray:
    """Cache text embeddings on disk (schema has no text-vector column)."""
    cache_path = EMB_CACHE_DIR / "text" / f"{entity_id}.npy"
    if cache_path.is_file() and not force:
        log.info("text cache hit %s", entity_id)
        loaded = np.load(cache_path)
        return _l2_normalize(loaded)
    vec = embed_text(text)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, vec)
    return vec


class ImageIndex:
    """Brute-force numpy cosine index over listing photo vectors."""

    def __init__(
        self,
        matrix: np.ndarray,
        meta: list[tuple[str, int, str]],
    ) -> None:
        self.matrix = np.asarray(matrix, dtype=np.float32)
        self.meta = meta

    @classmethod
    def build_from_db(cls, conn: sqlite3.Connection) -> ImageIndex:
        rows = conn.execute(
            """
            SELECT id, listing_id, path, clip_vec
            FROM listing_images
            WHERE clip_vec IS NOT NULL
            """
        ).fetchall()
        vecs: list[np.ndarray] = []
        meta: list[tuple[str, int, str]] = []
        for row in rows:
            blob = row["clip_vec"]
            if not blob:
                continue
            vecs.append(blob_to_vec(blob))
            meta.append((str(row["listing_id"]), int(row["id"]), str(row["path"])))
        if not vecs:
            return cls(np.zeros((0, 0), dtype=np.float32), [])
        return cls(np.stack(vecs, axis=0).astype(np.float32), meta)

    def query(
        self,
        query_vecs: np.ndarray,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """Max cosine per listing across any listing photo vs any query photo."""
        if self.matrix.size == 0 or not self.meta:
            return []
        queries = np.asarray(query_vecs, dtype=np.float32)
        if queries.size == 0:
            return []
        if queries.ndim == 1:
            queries = queries.reshape(1, -1)
        sims = self.matrix @ queries.T
        per_image_best = sims.max(axis=1)
        best: dict[str, float] = {}
        for score, (listing_id, _, _) in zip(per_image_best, self.meta, strict=True):
            value = float(score)
            prev = best.get(listing_id)
            if prev is None or value > prev:
                best[listing_id] = value
        ranked = sorted(best.items(), key=lambda item: item[1], reverse=True)
        return ranked[: max(0, int(top_k))]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT listing_id FROM listing_images
            ORDER BY listing_id, id
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            print("No listing images in the database.")
            return
        listing_id = str(row["listing_id"])
        written = embed_listing_images(conn, listing_id)
        image_row = conn.execute(
            """
            SELECT id, path, clip_vec FROM listing_images
            WHERE listing_id = ? AND clip_vec IS NOT NULL
            ORDER BY id
            LIMIT 1
            """,
            (listing_id,),
        ).fetchone()
        if image_row is None or image_row["clip_vec"] is None:
            print("No embedded listing photo.")
            return
        stored = blob_to_vec(image_row["clip_vec"])
        dim = int(stored.shape[0])
        print(f"vectors-written={written} image_dim={dim}")
        reco = embed_image(_resolve_image_path(image_row["path"]))
        self_sim = float(np.dot(stored, reco))
        print(f"self-similarity={self_sim:.6f}")
        assert abs(self_sim - 1.0) < 1e-3, self_sim

        listing = conn.execute(
            "SELECT description FROM listings WHERE id = ?",
            (listing_id,),
        ).fetchone()
        text_vec = embed_description_cached(listing_id, (listing["description"] if listing else "") or "")
        print(f"text_dim={int(text_vec.shape[0])}")

        index = ImageIndex.build_from_db(conn)
        query_vecs = np.stack(
            [
                blob_to_vec(item["clip_vec"])
                for item in conn.execute(
                    """
                    SELECT clip_vec FROM listing_images
                    WHERE listing_id = ? AND clip_vec IS NOT NULL
                    ORDER BY id
                    """,
                    (listing_id,),
                ).fetchall()
            ]
        )
        top3 = index.query(query_vecs, top_k=3)
        print("top-3", top3)
        assert top3, "empty index query"
        assert top3[0][0] == listing_id, top3
    finally:
        conn.close()


if __name__ == "__main__":
    main()
