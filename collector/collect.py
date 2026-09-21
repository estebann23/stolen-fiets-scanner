"""One-time local listing collection. Does not scrape Marktplaats.

Marktplaats terms forbid copying their advertisement database, and robots.txt
disallows `/lrp/api/search*`. The official API requires partner OAuth credentials
we do not have. This collector therefore:

1. Builds a synthetic, Marktplaats-*shaped* second-hand bike corpus for the demo, or
2. Imports a user-supplied JSONL (`--import-jsonl`) from a permitted manual dump.

Listings are filtered, capped, written to `data/raw/listings.jsonl`, given
placeholder photos, and loaded into SQLite.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collector.demo_corpus import build_demo_listings  # noqa: E402
from collector.relevance_filter import filter_listings  # noqa: E402
from config import IMAGES_DIR, QUERIES_PATH, RAW_LISTINGS_PATH  # noqa: E402
from db import import_listings_jsonl, init_schema  # noqa: E402

COLOR_RGB: dict[str, tuple[int, int, int]] = {
    "black": (32, 32, 32),
    "grey": (120, 120, 120),
    "blue": (40, 80, 160),
    "green": (40, 120, 70),
    "white": (230, 230, 230),
    "red": (170, 40, 40),
    "silver": (180, 180, 190),
    "anthracite": (60, 60, 65),
}


def load_queries(path: Path = QUERIES_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_import_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_placeholder_images(listing: dict[str, Any], n_photos: int = 2) -> list[str]:
    listing_id = listing["id"]
    out_dir = IMAGES_DIR / listing_id
    out_dir.mkdir(parents=True, exist_ok=True)
    color = listing.get("color") if listing.get("color") in COLOR_RGB else "grey"
    rgb = COLOR_RGB[color]
    text = listing.get("title", listing_id)[:40]
    paths: list[str] = []
    for index in range(n_photos):
        img = Image.new("RGB", (640, 480), rgb)
        draw = ImageDraw.Draw(img)
        fg = (255, 255, 255) if sum(rgb) < 400 else (20, 20, 20)
        draw.rectangle((40, 40, 600, 440), outline=fg, width=4)
        draw.ellipse((80, 280, 220, 420), outline=fg, width=8)
        draw.ellipse((400, 280, 540, 420), outline=fg, width=8)
        try:
            font = ImageFont.load_default()
        except OSError:
            font = None
        draw.text((60, 60), text, fill=fg, font=font)
        draw.text((60, 90), f"photo {index}", fill=fg, font=font)
        rel = Path("data") / "images" / listing_id / f"{index}.jpg"
        dest = ROOT / rel
        img.save(dest, format="JPEG", quality=75)
        paths.append(rel.as_posix())
    return paths


def persist_jsonl(listings: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in listings:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def collect(import_jsonl: Path | None = None, seed: int = 42) -> list[dict[str, Any]]:
    queries = load_queries()
    max_listings = int(queries.get("max_listings") or 250)
    rng = random.Random(seed)

    if import_jsonl is not None:
        raw = load_import_jsonl(import_jsonl)
        print(f"imported {len(raw)} rows from {import_jsonl}")
    else:
        raw = build_demo_listings(
            brands=list(queries["brands"]),
            types=list(queries["types"]),
            rng=rng,
            n_keep=max_listings + 10,
            n_junk=40,
        )
        print(f"generated {len(raw)} demo rows (including junk to filter)")

    cleaned = filter_listings(raw)
    dropped = len(raw) - len(cleaned)
    cleaned = cleaned[:max_listings]
    print(f"relevance filter dropped {dropped}; keeping {len(cleaned)}")

    for row in cleaned:
        n_photos = 3 if row.get("marks") else 2
        row["image_paths"] = write_placeholder_images(row, n_photos=n_photos)

    persist_jsonl(cleaned, RAW_LISTINGS_PATH)
    init_schema()
    imported = import_listings_jsonl(RAW_LISTINGS_PATH)
    print(f"wrote {RAW_LISTINGS_PATH} and loaded {imported} listings into SQLite")
    return cleaned


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect and clean the local listing dataset.")
    parser.add_argument(
        "--import-jsonl",
        type=Path,
        default=None,
        help="Optional local JSONL dump (manual collection). Not used to scrape Marktplaats.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    collect(import_jsonl=args.import_jsonl, seed=args.seed)


if __name__ == "__main__":
    main()
