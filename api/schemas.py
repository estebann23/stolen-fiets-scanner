"""Pydantic models for API I/O (SPEC §6–§8)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["likely_same", "possibly_same", "different"]


class HealthResponse(BaseModel):
    status: str
    listings: int


class ListingAttributes(BaseModel):
    listing_id: str
    brand: str | None = None
    model: str | None = None
    bike_type: str | None = None
    colors: list[str] | None = None
    frame_shape: str | None = None
    wheel_size: str | None = None
    is_electric: bool | None = None
    accessories: list[str] | None = None
    marks: list[str] | None = None
    serial_found: str | None = None


class ListingDetail(BaseModel):
    id: str
    title: str | None = None
    description: str | None = None
    price: float | None = None
    location: str | None = None
    lat: float | None = None
    lon: float | None = None
    posted_at: str | None = None
    seller_id: str | None = None
    url: str | None = None
    suspicion_score: float | None = None
    images: list[str] = Field(default_factory=list)
    attributes: ListingAttributes | None = None


class MatchCandidate(BaseModel):
    listing_id: str
    url: str | None = None
    score: float
    serial_match: bool
    verdict: Verdict | None = None
    reasons: list[str] = Field(default_factory=list)
    suspicion_score: float | None = None
    listing_image: str | None = None
    report_image: str | None = None


class MatchResponse(BaseModel):
    report_id: str
    candidates: list[MatchCandidate]


class ReportCreated(BaseModel):
    report_id: str
