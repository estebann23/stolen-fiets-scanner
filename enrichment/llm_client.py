"""Single helper for all VLM calls (SPEC §11): retries, timeout, JSON, disk cache."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI

from config import (
    GEMINI_BASE_URL,
    GOOGLE_API_KEY,
    LLM_CACHE_DIR,
    LLM_TIMEOUT_S,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    VLM_MODEL,
)

log = logging.getLogger(__name__)

SETUP_HINT = (
    "Set OPENROUTER_API_KEY or GOOGLE_API_KEY, and VLM_MODEL, in .env "
    "(see .env.example). Do not commit secrets."
)


def vlm_ready() -> bool:
    return bool((OPENROUTER_API_KEY or GOOGLE_API_KEY) and VLM_MODEL)


def require_vlm_config() -> None:
    missing: list[str] = []
    if not OPENROUTER_API_KEY and not GOOGLE_API_KEY:
        missing.append("OPENROUTER_API_KEY or GOOGLE_API_KEY")
    if not VLM_MODEL:
        missing.append("VLM_MODEL")
    if missing:
        raise RuntimeError(f"Missing env var(s): {', '.join(missing)}. {SETUP_HINT}")


def parse_json_loose(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from model text; strip fences and find the first `{...}`."""
    if not text or not str(text).strip():
        return None
    cleaned = str(text).strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    blob = _first_balanced_object(cleaned)
    if blob is None:
        return None
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _first_balanced_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _mime_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    return "image/jpeg"


def _image_part(path: Path) -> dict[str, Any]:
    mime = _mime_for(path)
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{b64}"},
    }


def _cache_key(system: str, user_text: str, image_paths: list[Path]) -> str:
    hasher = hashlib.sha256()
    hasher.update(VLM_MODEL.encode("utf-8"))
    hasher.update(system.encode("utf-8"))
    hasher.update(user_text.encode("utf-8"))
    for path in image_paths:
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _cache_path(key: str) -> Path:
    return LLM_CACHE_DIR / f"{key}.json"


def _load_cache(key: str) -> dict[str, Any] | None:
    path = _cache_path(key)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    parsed = payload.get("parsed")
    if isinstance(parsed, dict):
        return parsed
    return None


def _write_cache(key: str, raw_content: str, parsed: dict[str, Any]) -> None:
    LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": VLM_MODEL,
        "key": key,
        "raw_content": raw_content,
        "parsed": parsed,
    }
    _cache_path(key).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _client(timeout_s: float) -> OpenAI:
    if GOOGLE_API_KEY and not OPENROUTER_API_KEY:
        return OpenAI(
            base_url=GEMINI_BASE_URL,
            api_key=GOOGLE_API_KEY,
            timeout=timeout_s,
        )
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
        timeout=timeout_s,
    )


def call_vlm_json(
    system: str,
    user_text: str,
    image_paths: list[Path],
    *,
    max_retries: int = 1,
    timeout_s: float | None = None,
) -> dict[str, Any] | None:
    """Call the configured VLM and return parsed JSON, or None after retries fail."""
    require_vlm_config()
    timeout = float(LLM_TIMEOUT_S if timeout_s is None else timeout_s)
    paths = [Path(p) for p in image_paths]
    key = _cache_key(system, user_text, paths)
    cached = _load_cache(key)
    if cached is not None:
        log.info("vlm cache hit key=%s images=%s", key[:12], len(paths))
        return cached

    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for path in paths:
        user_content.append(_image_part(path))

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    attempts = max_retries + 1
    client = _client(timeout)
    for attempt in range(1, attempts + 1):
        log.info(
            "vlm attempt %s/%s model=%s images=%s timeout_s=%s",
            attempt,
            attempts,
            VLM_MODEL,
            len(paths),
            timeout,
        )
        try:
            response = client.chat.completions.create(
                model=VLM_MODEL,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            raw = ""
            if response.choices:
                message = response.choices[0].message
                raw = (message.content or "") if message is not None else ""
            if not raw.strip():
                log.info("vlm empty response attempt=%s/%s", attempt, attempts)
                continue
            parsed = parse_json_loose(raw)
            if parsed is None:
                log.info("vlm json parse failure attempt=%s/%s", attempt, attempts)
                continue
            _write_cache(key, raw, parsed)
            return parsed
        except (APITimeoutError, TimeoutError) as exc:
            log.info("vlm timeout attempt=%s/%s err=%s", attempt, attempts, type(exc).__name__)
        except APIConnectionError as exc:
            log.info("vlm network error attempt=%s/%s err=%s", attempt, attempts, type(exc).__name__)
        except Exception as exc:  # noqa: BLE001 — last-resort retry, never leak secrets
            log.info("vlm error attempt=%s/%s err=%s", attempt, attempts, type(exc).__name__)
    return None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not vlm_ready():
        print(SETUP_HINT)
        sys.exit(0)
    result = call_vlm_json(
        "Return a JSON object and nothing else.",
        'Reply with {"ok": true}',
        [],
    )
    print(result)


if __name__ == "__main__":
    main()
