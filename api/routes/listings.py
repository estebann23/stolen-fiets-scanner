"""Listing detail routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import ListingAttributes, ListingDetail
from db import fetch_listing

router = APIRouter()


@router.get("/listings/{listing_id}", response_model=ListingDetail)
def get_listing(listing_id: str) -> ListingDetail:
    row = fetch_listing(listing_id)
    if row is None:
        raise HTTPException(status_code=404, detail="listing not found")
    attributes = None
    raw_attrs = row.get("attributes")
    if raw_attrs:
        attributes = ListingAttributes.model_validate(raw_attrs)
    return ListingDetail(
        id=row["id"],
        title=row.get("title"),
        description=row.get("description"),
        price=row.get("price"),
        location=row.get("location"),
        lat=row.get("lat"),
        lon=row.get("lon"),
        posted_at=row.get("posted_at"),
        seller_id=row.get("seller_id"),
        url=row.get("url"),
        suspicion_score=row.get("suspicion_score"),
        images=row.get("images") or [],
        attributes=attributes,
    )
