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

## Dataset (one-time)

Listings come from a **single** Apify run of `haketa/marktplaats-scraper` (token in `.env.local`, never committed): fietsen around Maastricht (postcode `6211`), 25 km, 200–500 ads.

```bash
python collector/collect.py --source apify
```

That writes `data/raw/listings.jsonl`, downloads photos, and loads `data/bike.db`. Demo corpus / JSONL import still work:

```bash
python collector/collect.py --source demo
python collector/collect.py --import-jsonl path/to/dump.jsonl
python db.py
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
