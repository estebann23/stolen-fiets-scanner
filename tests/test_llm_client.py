"""SPEC 11: every VLM call goes through llm_client (loose JSON parse, cache, config gate)."""

from __future__ import annotations

import json

import pytest

import enrichment.llm_client as llm
from enrichment.llm_client import parse_json_loose


def test_parse_plain_object():
    assert parse_json_loose('{"a": 1}') == {"a": 1}


def test_parse_fenced_json_block():
    assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_loose('```\n{"a": 1}\n```') == {"a": 1}


def test_parse_object_with_surrounding_prose():
    assert parse_json_loose('Sure! Here it is:\n{"verdict": "different"}\nHope that helps.') == {
        "verdict": "different"
    }


def test_parse_handles_nested_objects_and_braces_in_strings():
    payload = {"a": {"b": [1, 2]}, "note": "a } brace { inside"}
    assert parse_json_loose(f"noise {json.dumps(payload)} noise") == payload


def test_parse_rejects_non_objects_and_garbage():
    assert parse_json_loose("") is None
    assert parse_json_loose("   ") is None
    assert parse_json_loose(None) is None
    assert parse_json_loose("[1, 2, 3]") is None
    assert parse_json_loose("no json here") is None
    assert parse_json_loose('{"broken": ') is None


def test_vlm_ready_requires_a_key_and_a_model(monkeypatch):
    monkeypatch.setattr(llm, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(llm, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(llm, "VLM_MODEL", "")
    assert llm.vlm_ready() is False

    monkeypatch.setattr(llm, "OPENROUTER_API_KEY", "k")
    assert llm.vlm_ready() is False

    monkeypatch.setattr(llm, "VLM_MODEL", "some/model")
    assert llm.vlm_ready() is True


def test_require_vlm_config_names_the_missing_vars(monkeypatch):
    monkeypatch.setattr(llm, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(llm, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(llm, "VLM_MODEL", "")
    with pytest.raises(RuntimeError) as excinfo:
        llm.require_vlm_config()
    assert "OPENROUTER_API_KEY or GOOGLE_API_KEY" in str(excinfo.value)
    assert "VLM_MODEL" in str(excinfo.value)


def test_cache_roundtrip_avoids_a_second_call(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "LLM_CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "VLM_MODEL", "test/model")
    key = llm._cache_key("sys", "user", [])
    assert llm._load_cache(key) is None
    llm._write_cache(key, '{"ok": true}', {"ok": True})
    assert llm._load_cache(key) == {"ok": True}


def test_cache_key_depends_on_prompt_model_and_images(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "VLM_MODEL", "test/model")
    base = llm._cache_key("sys", "user", [])
    assert llm._cache_key("sys2", "user", []) != base
    assert llm._cache_key("sys", "user2", []) != base
    monkeypatch.setattr(llm, "VLM_MODEL", "other/model")
    assert llm._cache_key("sys", "user", []) != base


def test_cache_key_includes_image_bytes(tmp_path, monkeypatch, photo_jpeg):
    monkeypatch.setattr(llm, "VLM_MODEL", "test/model")
    first = tmp_path / "a.jpg"
    second = tmp_path / "b.jpg"
    first.write_bytes(photo_jpeg)
    second.write_bytes(photo_jpeg + b"\x00")
    assert llm._cache_key("s", "u", [first]) != llm._cache_key("s", "u", [second])


def test_corrupt_cache_file_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "LLM_CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "VLM_MODEL", "test/model")
    key = llm._cache_key("sys", "user", [])
    llm._cache_path(key).write_text("not json", encoding="utf-8")
    assert llm._load_cache(key) is None
