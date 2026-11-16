"""
Module: test_pillars_bypass_cache
Layer: demo_game (tests)
Purpose: The live pillar eval must drive every dialogue beat through the engine.
         A disk-cache hit returns early before POST /v1/dialogue, so a warm
         demo_game/.cache/demo let the 2026-10-22 run judge pillars on dialogue
         the engine never saw (T25.6).
Dependencies: demo_game.runners.run, demo_game.runners.pillars
Used by: make test-demo
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from demo_game.runners import run as run_module
from demo_game.runners.pillars import _run_demo_with_recorder
from demo_game.runners.run import LLMCache


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the module cache directory at a temporary folder."""
    monkeypatch.setattr(run_module, "CACHE_DIR", tmp_path)
    return tmp_path


def test_disabled_cache_never_serves_a_hit(cache_dir: Path) -> None:
    """An entry on disk is ignored when the cache is disabled."""
    LLMCache().put("mira_innkeeper", "hello", {"npc_response": "cached reply"})

    assert LLMCache().get("mira_innkeeper", "hello") is not None
    assert LLMCache(enabled=False).get("mira_innkeeper", "hello") is None


def test_disabled_cache_never_writes(cache_dir: Path) -> None:
    """A disabled cache leaves the directory untouched, so it cannot warm later runs."""
    LLMCache(enabled=False).put("mira_innkeeper", "hello", {"npc_response": "live"})

    assert list(cache_dir.iterdir()) == []


def test_pillar_run_uses_a_disabled_cache() -> None:
    """The pillar eval builds its DemoRunner with a cache that serves no hits."""
    with patch.object(run_module, "DemoRunner") as runner_cls:
        error = _run_demo_with_recorder(recorder=object())

    assert error is None
    cache = runner_cls.call_args.kwargs["cache"]
    assert isinstance(cache, LLMCache)
    assert cache.enabled is False
