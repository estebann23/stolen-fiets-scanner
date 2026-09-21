"""Project config loaded from `.env` (SPEC §3 and §11)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local", override=True)

DB_PATH = Path(os.getenv("DB_PATH", "data/bike.db"))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH

API_URL = os.getenv("API_URL", "http://localhost:8000")
CLIP_MODEL = os.getenv("CLIP_MODEL", "ViT-B-32")
VLM_MODEL = os.getenv("VLM_MODEL", "")

DATA_DIR = ROOT / "data"
RAW_LISTINGS_PATH = DATA_DIR / "raw" / "listings.jsonl"
IMAGES_DIR = DATA_DIR / "images"
REPORTS_DIR = DATA_DIR / "reports"
QUERIES_PATH = ROOT / "collector" / "queries.yaml"

APIFY_API_TOKEN = (
    os.getenv("APIFY_API_TOKEN")
    or os.getenv("APIFY_KEY")
    or ""
).strip().strip('"')
APIFY_MARKTPLAATS_ACTOR_ID = os.getenv(
    "APIFY_MARKTPLAATS_ACTOR_ID",
    "haketa/marktplaats-scraper",
)
APIFY_DATASET_ID = os.getenv("APIFY_DATASET_ID", "")

MATCH_RADIUS_KM = 25.0
MATCH_WEIGHTS = {
    "image": 0.45,
    "attributes": 0.30,
    "marks": 0.15,
    "text": 0.10,
}
