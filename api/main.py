"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.listings import router as listings_router
from api.routes.reports import router as reports_router
from api.schemas import HealthResponse
from db import init_schema, listing_count

app = FastAPI(title="Stolen Bike Matcher", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(listings_router)
app.include_router(reports_router)


@app.on_event("startup")
def on_startup() -> None:
    init_schema()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", listings=listing_count())
