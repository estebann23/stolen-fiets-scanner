# Stolen Bike Matcher — web frontend

Civic intake + results UI for the FastAPI matcher. Results are **candidates for
police review**, never accusations. The Streamlit app in `app/` remains a fallback.

## Run with the API

From the **repo root**, start the backend:

```bash
uvicorn api.main:app --reload
```

In another terminal:

```bash
cd frontend
cp .env.local.example .env.local   # optional; default is already http://localhost:8000
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Submit a report on `/`; after
matching, you land on `/reports/{id}` (refresh uses `GET /reports/{id}/matches`).

Photos render from `${NEXT_PUBLIC_API_URL}/data/...` (FastAPI serves the repo
`data/` directory read-only).

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Next.js on port 3000 |
| `npm run build` | Production build (type-checked) |
| `npm start` | Serve the production build |

`NEXT_PUBLIC_API_URL` is the only frontend env var (no secrets).
