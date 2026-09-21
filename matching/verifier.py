"""VLM pairwise 'same bike?' rerank of top candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from config import ROOT
from enrichment.llm_client import call_vlm_json

VerdictLabel = Literal["likely_same", "possibly_same", "different"]

VERIFY_PROMPT = """You compare stolen-bike report photos with a marketplace listing.
Are these the SAME physical bicycle?
Reply with STRICT JSON only:
{"verdict": "likely_same" | "possibly_same" | "different", "reasons": [string], "confidence": number}
Keep reasons short. If unsure, use possibly_same. Do not invent unique marks that are not visible.
"""

_VERDICT_RANK = {
    "likely_same": 0,
    "possibly_same": 1,
    None: 2,
    "different": 3,
}


class Verdict(BaseModel):
    verdict: VerdictLabel
    reasons: list[str] = Field(default_factory=list)
    confidence: float = 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, number))

    @field_validator("reasons", mode="before")
    @classmethod
    def _coerce_reasons(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value]
        return []


def _resolve(raw: Path | str) -> Path:
    """DB photo paths are posix and relative to the repo root, not to os.getcwd()."""
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def verify_pair(
    report_image_paths: list[Path],
    listing_image_paths: list[Path],
) -> Verdict | None:
    candidates = [_resolve(p) for p in report_image_paths[:3]]
    candidates += [_resolve(p) for p in listing_image_paths[:3]]
    paths = [path for path in candidates if path.is_file()]
    if not paths:
        return None
    try:
        parsed = call_vlm_json(
            VERIFY_PROMPT,
            "Report photos come first, then listing photos. Same physical bike?",
            paths,
        )
    except Exception:  # noqa: BLE001 — degrade when the VLM is unavailable
        return None
    if not isinstance(parsed, dict):
        return None
    try:
        return Verdict.model_validate(parsed)
    except ValidationError:
        return None


def rerank(report: dict[str, Any], scored: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    ordered = sorted(
        scored,
        key=lambda item: (-float(item.get("score") or 0.0), str(item.get("listing_id") or "")),
    )
    verify_ids = {item["listing_id"] for item in ordered[: max(0, int(top_k))]}
    report_paths = [Path(p) for p in report.get("images") or []]

    for item in ordered:
        if item.get("serial_match"):
            item["verdict_obj"] = Verdict(
                verdict="likely_same",
                reasons=["exact serial match"],
                confidence=1.0,
            )
            item["verdict"] = "likely_same"
            continue
        if item["listing_id"] not in verify_ids:
            item["verdict_obj"] = None
            item["verdict"] = None
            continue
        listing = item.get("listing") or {}
        listing_paths = [Path(p) for p in listing.get("image_paths") or []]
        verdict = verify_pair(report_paths, listing_paths)
        item["verdict_obj"] = verdict
        item["verdict"] = None if verdict is None else verdict.verdict

    ordered.sort(
        key=lambda item: (
            _VERDICT_RANK.get(item.get("verdict"), 2),
            -float(item.get("score") or 0.0),
            str(item.get("listing_id") or ""),
        )
    )
    return ordered


def main() -> None:
    sample = Verdict(verdict="possibly_same", reasons=["similar frame"], confidence=0.4)
    print(sample.model_dump())


if __name__ == "__main__":
    main()
