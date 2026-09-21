# Stolen Bike Matcher

Hackathon prototype: match a stolen-bike report (photos + serial + theft date/location) against a **fixed local dataset** of second-hand listings. Outputs are candidates for police review, not accusations.

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

## Dataset (offline)

Marktplaats listings are **not scraped**. Their terms and robots.txt forbid copying the ad database and using `/lrp/api/search`. The official API needs partner OAuth credentials.

```bash
python collector/collect.py
```

This builds ~250 filtered demo listings (placeholder photos), writes `data/raw/listings.jsonl`, and loads `data/bike.db`. To use a manual JSONL dump you already have:

```bash
python collector/collect.py --import-jsonl path/to/dump.jsonl
```

```bash
python db.py   # schema only / re-import jsonl
```

## API

```bash
uvicorn api.main:app --reload
```

- `GET /health`
- `GET /listings/{id}` (e.g. `m_0001`)
- Report/match routes return 501 until matching is built

## UI mockup

```bash
streamlit run app/streamlit_app.py
```
