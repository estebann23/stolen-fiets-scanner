# Stolen Bike Matcher

Hackathon prototype: match a stolen-bike report (photos, optional serial, theft date/location) against a **fixed local Marktplaats corpus**. Results are **candidates for police review**, not accusations.

`SPEC.md` is the source of truth for schema, matching, and API behaviour.

## What works today

- One-time listing collect (Apify, demo, or JSONL) → `data/bike.db` (~235 ads around Maastricht after filters)
- Offline enrichment: VLM attributes, local CLIP embeddings, serial OCR, suspicion score
- FastAPI: health, listing detail, report intake, match + cached results
- Streamlit: report **form mockup only** (does not call the API yet)
- Eval scripts: not implemented

`suspicion_score` is display-only and is never part of the match score.

## Layout

```
data/          JSONL, listing/report photos, SQLite, caches (gitignored under data/cache/)
collector/     Apify / demo / JSONL collect + relevance filter
enrichment/    llm_client, attributes, CLIP, serial OCR, risk, batch runner
matching/      filters, weighted score, VLM rerank, explanations
api/           FastAPI
app/           Streamlit mockup
db.py          schema + helpers
config.py      models, paths, MATCH_* / RISK_* weights
```

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put secrets in **`.env.local`** (gitignored), not in git:

```
OPENROUTER_API_KEY=sk-or-...
VLM_MODEL=qwen/qwen2.5-vl-72b-instruct
APIFY_KEY=apify_api_...
```

OpenRouter is the default VLM path. If `OPENROUTER_API_KEY` is unset, `GOOGLE_API_KEY` + a Gemini `VLM_MODEL` can be used instead. CLIP runs **locally** (`torch` + `open-clip-torch`); the first encode downloads ViT-B-32 weights (~350MB).

## Dataset (one-time)

Maastricht postcode `6211`, 25 km, fiets category, up to 300 raw ads via Apify `haketa/marktplaats-scraper`:

```bash
python collector/collect.py --source apify
```

Writes `data/raw/listings.jsonl`, photos under `data/images/`, and replaces listing rows in `data/bike.db`. Alternatives:

```bash
python collector/collect.py --source demo
python collector/collect.py --import-jsonl path/to/dump.jsonl
python db.py
```

## Enrichment (idempotent)

```bash
python -m enrichment.run_enrichment
python -m enrichment.run_enrichment --limit 5
python -m enrichment.run_enrichment --only embeddings
```

`--force` recomputes. `--only` is one of `attributes`, `embeddings`, `serial`, `risk`. Attributes and serial OCR need a VLM key; embeddings and risk do not. Smoke tests:

```bash
python -m enrichment.attributes
python -m enrichment.embeddings
python -m enrichment.serial_ocr
python -m enrichment.risk_signals
```

Text CLIP vectors are cached as `data/cache/embeddings/text/{id}.npy`. VLM responses as `data/cache/llm/*.json`.

## API

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

| Method | Path |
|---|---|
| `GET` | `/health` |
| `GET` | `/listings/{id}` |
| `POST` | `/reports` (multipart, 1–5 photos, `stolen_at` required) |
| `POST` | `/reports/{id}/match` |
| `GET` | `/reports/{id}/matches` |

Create a report and match (PowerShell-friendly):

```bash
curl -s -X POST http://127.0.0.1:8000/reports ^
  -F "stolen_at=2026-09-01" ^
  -F "location=Maastricht" ^
  -F "photos=@data/images/m2339783810/0.jpg;type=image/jpeg"

curl -s -X POST http://127.0.0.1:8000/reports/{report_id}/match
curl -s http://127.0.0.1:8000/reports/{report_id}/matches
```

Matching: 25 km radius, weights 0.45 image / 0.30 attributes / 0.15 marks / 0.10 text, serial override to score `1.0`, VLM rerank of the top 10, return top 5. Without a VLM key, intake and matching still run on CLIP image + text.

## UI mockup

```bash
streamlit run app/streamlit_app.py
```

Validates the form locally; it does **not** POST to FastAPI or show ranked listings yet.

## Notes

- Do not commit `.env.local`, `data/cache/`, or API keys.
- Listing ids are Marktplaats-style (`m…`); report ids are `r_` + 8 hex characters.
- Full-corpus CLIP/VLM enrichment is optional per listing; `/match` still scores whatever vectors exist.
