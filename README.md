# Stolen Bike Matcher

Hackathon prototype: match a stolen-bike report (photos + serial + theft date/location) against a fixed local dataset of second-hand listings. Outputs are candidates for police review, not accusations.

See `SPEC.md` for architecture, data model, API, and build order.

## Layout

```
data/          listings, photos, SQLite
collector/     one-time listing collection
enrichment/    VLM attributes, embeddings, OCR, risk signals
matching/      filters, scoring, VLM rerank, explanations
api/           FastAPI
app/           Streamlit UI
eval/          synthetic reports and metrics
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

No live scraping. Fill `.env` before running enrichment or matching.
