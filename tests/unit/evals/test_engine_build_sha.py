"""
Module: test_engine_build_sha
Layer: tests (eval harness unit)
Purpose: Verify T16.4 — RunConfig and TrendRow carry the engine's build SHA from
         GET /health data.version, independent of the client's git_sha.
         An unreachable /health is non-fatal; engine_build_sha records None.
Dependencies: engine_adapter, run_config, trend_store (evals/).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from run_config import RunConfig, resolve_run_config
from trend_store import TrendRow

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DIALOGUE_LLM_CONFIG = (
    _REPO_ROOT / "src" / "npc_engine" / "engines" / "dialogue" / "llm_config.yaml"
)

_STUB_BUILD_SHA = "abc1234"


def _offline_probes(**overrides: object) -> dict:
    """Return resolve_run_config kwargs that never touch the network."""
    probes: dict = {
        "fetch_generation_digest": lambda _m, _u: "sha256:stub-generation",
        "fetch_judge_digest": lambda _m, _u: "sha256:stub-judge",
        "fetch_ollama_version_fn": lambda _u: "0.0.0-stub",
        "fetch_corpus_fingerprint": lambda: None,
        "fetch_build_sha_fn": lambda: _STUB_BUILD_SHA,
    }
    probes.update(overrides)
    return probes


# ---------------------------------------------------------------------------
# Field existence — RED anchor: fails today because the field doesn't exist
# ---------------------------------------------------------------------------


def test_run_config_has_engine_build_sha_field() -> None:
    """RunConfig must declare engine_build_sha as a first-class field (T16.4)."""
    assert "engine_build_sha" in RunConfig.model_fields


def test_trend_row_has_engine_build_sha_field() -> None:
    """TrendRow must declare engine_build_sha as a first-class field (T16.4)."""
    assert "engine_build_sha" in TrendRow.model_fields


# ---------------------------------------------------------------------------
# resolve_run_config carries the engine sha from the stub
# ---------------------------------------------------------------------------


def test_resolve_run_config_carries_engine_build_sha() -> None:
    """resolve_run_config records the sha returned by the stub /health fetcher."""
    config = resolve_run_config(config_path=_DIALOGUE_LLM_CONFIG, **_offline_probes())
    assert config.engine_build_sha == _STUB_BUILD_SHA


def test_engine_build_sha_none_when_health_unreachable() -> None:
    """An unreachable /health must not stop a run — engine_build_sha is None, not fatal."""
    config = resolve_run_config(
        config_path=_DIALOGUE_LLM_CONFIG,
        **_offline_probes(fetch_build_sha_fn=lambda: None),
    )
    assert config.engine_build_sha is None


def test_engine_build_sha_and_git_sha_are_independent() -> None:
    """The two sha fields exist side by side; they are independent and can differ."""
    config = resolve_run_config(config_path=_DIALOGUE_LLM_CONFIG, **_offline_probes())
    assert config.engine_build_sha == _STUB_BUILD_SHA
    assert len(config.git_sha) == 7  # client-side git sha, unchanged


# ---------------------------------------------------------------------------
# fetch_build_sha in engine_adapter — total (returns None on failure)
# ---------------------------------------------------------------------------


def test_fetch_build_sha_returns_none_on_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_build_sha is total — returns None when the engine is unreachable."""
    import httpx
    from engine_adapter import fetch_build_sha

    def _raise(*_a: object, **_k: object) -> None:
        raise httpx.ConnectError("unreachable")

    monkeypatch.setattr(httpx, "get", _raise)
    result = fetch_build_sha("http://localhost:9999", "test-key")
    assert result is None


def test_fetch_build_sha_extracts_data_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_build_sha reads data.version from a well-formed /health response."""
    import httpx
    from engine_adapter import fetch_build_sha

    class _FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"success": True, "data": {"status": "ok", "version": "deadbee"}}

    monkeypatch.setattr(httpx, "get", lambda *_a, **_k: _FakeResp())
    result = fetch_build_sha("http://localhost:8001", "test-key")
    assert result == "deadbee"


def test_fetch_build_sha_returns_none_when_version_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_build_sha returns None when data.version is missing from the response."""
    import httpx
    from engine_adapter import fetch_build_sha

    class _FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"success": True, "data": {"status": "ok"}}

    monkeypatch.setattr(httpx, "get", lambda *_a, **_k: _FakeResp())
    result = fetch_build_sha("http://localhost:8001", "test-key")
    assert result is None


# ---------------------------------------------------------------------------
# TrendRow backward compatibility
# ---------------------------------------------------------------------------


def test_trend_row_without_engine_build_sha_still_loads() -> None:
    """Rows written before T16.4 (no engine_build_sha) must still parse."""
    row = TrendRow(
        gen_id="gen-legacy",
        harness_version="aabbcc112233",
        recorded_at="2026-10-20T00:00:00+00:00",
    )
    assert row.engine_build_sha is None
