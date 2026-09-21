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
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
GOOGLE_API_KEY = (
    os.getenv("GOOGLE_API_KEY")
    or os.getenv("Google_API_KEY")
    or os.getenv("GEMINI_API_KEY")
    or ""
).strip().strip('"')
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
)
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "60"))

DATA_DIR = ROOT / "data"
LLM_CACHE_DIR = Path(os.getenv("LLM_CACHE_DIR", str(DATA_DIR / "cache" / "llm")))
if not LLM_CACHE_DIR.is_absolute():
    LLM_CACHE_DIR = ROOT / LLM_CACHE_DIR
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
