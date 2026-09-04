"""
Module: test_engine_adapter
Layer: test (unit)
Purpose: Pin fetch_model_digest's contract against Ollama's actual /api/tags shape
    (ISSUE-286) — /api/show stopped carrying a top-level 'digest' field on Ollama
    >=0.33, which made R2.1's digest gate unconditionally fatal.
Dependencies: engine_adapter, monkeypatch (patches the shared httpx module — the
    function under test does `import httpx` locally, so patching the module
    object's `get` attribute is the only injection point available).
Used by: N/A (leaf test module).

Does NOT: hit a real Ollama server. No network I/O.
"""

from __future__ import annotations

import httpx
import pytest

from engine_adapter import fetch_model_digest

_OLLAMA_URL = "http://localhost:11434"

# Shape of a real GET /api/tags response (Ollama 0.33.2), trimmed to the fields
# fetch_model_digest reads.
_TAGS_RESPONSE = {
    "models": [
        {"name": "llama3.1:8b", "model": "llama3.1:8b", "digest": "aaa111"},
        {"name": "qwen2.5:7b", "model": "qwen2.5:7b", "digest": "845dbda0ea48"},
    ]
}


def _patch_get(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> None:
    """Replace httpx.get with a stub returning `response`, ignoring call args."""

    def _fake_get(*_args: object, **_kwargs: object) -> httpx.Response:
        return response

    monkeypatch.setattr(httpx, "get", _fake_get)


def test_fetch_model_digest_matches_tag_in_api_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model tag present in GET /api/tags returns that entry's digest.

    Regression for ISSUE-286: the prior implementation read POST /api/show's
    top-level 'digest' key, which Ollama 0.33.2 no longer sends for any model —
    this response has no such key and would previously have produced None here.
    """
    response = httpx.Response(200, json=_TAGS_RESPONSE, request=httpx.Request("GET", _OLLAMA_URL))
    _patch_get(monkeypatch, response)

    digest = fetch_model_digest("qwen2.5:7b", _OLLAMA_URL)

    assert digest == "845dbda0ea48"


def test_fetch_model_digest_returns_none_for_unlisted_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model tag absent from GET /api/tags returns None rather than raising."""
    response = httpx.Response(200, json=_TAGS_RESPONSE, request=httpx.Request("GET", _OLLAMA_URL))
    _patch_get(monkeypatch, response)

    digest = fetch_model_digest("not-pulled:latest", _OLLAMA_URL)

    assert digest is None


def test_fetch_model_digest_returns_none_when_ollama_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connection failure returns None rather than raising (stays total)."""

    def _raise_get(*_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", _raise_get)

    digest = fetch_model_digest("qwen2.5:7b", _OLLAMA_URL)

    assert digest is None
