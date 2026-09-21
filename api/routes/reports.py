"""Report intake and matching routes (stubs until matching is wired)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import MatchResponse, ReportCreated

router = APIRouter()


@router.post("/reports", response_model=ReportCreated)
def create_report() -> ReportCreated:
    raise HTTPException(status_code=501, detail="report intake not implemented yet")


@router.post("/reports/{report_id}/match", response_model=MatchResponse)
def run_match(report_id: str) -> MatchResponse:
    raise HTTPException(status_code=501, detail="matching not implemented yet")


@router.get("/reports/{report_id}/matches", response_model=MatchResponse)
def get_matches(report_id: str) -> MatchResponse:
    raise HTTPException(status_code=501, detail="matching not implemented yet")
