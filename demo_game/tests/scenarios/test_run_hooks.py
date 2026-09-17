"""
Tests for the two DemoRunner extension points used by scripts/demo_run_live.py (T2.4).

Verifies:
- DemoRunner accepts an injected LLMCache instead of building its own.
- DemoRunner.run(on_scene=...) calls the hook once per scene, before that scene executes.
- The default path (no cache, no hook) is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

import pytest

import demo_game.runners.run as run_module
from demo_game.runners.run import DemoRunner, LLMCache
from demo_game.runners.run_scenes import Scene


@dataclass
class _RecordingScene(Scene):
    """Scene that appends its name to a shared journal when executed."""

    journal: list[str] | None = None

    def execute(self, runner: DemoRunner) -> None:
        """Record execution order."""
        assert self.journal is not None
        self.journal.append(f"exec:{self.name}")


@dataclass
class _ExplodingScene(Scene):
    """Scene that raises, to prove the hook fires before execute."""

    def execute(self, runner: DemoRunner) -> None:
        """Raise unconditionally."""
        raise RuntimeError("boom")


def _runner(cache: LLMCache | None = None) -> DemoRunner:
    with patch.object(run_module, "DemoConfig") as cfg, patch.object(run_module, "EngineClient"):
        cfg.return_value.NPC_BASE_URL = "http://test"
        cfg.return_value.NPC_API_KEY = "k"
        return DemoRunner(dry_run=True, cache=cache)


def test_injected_cache_is_used() -> None:
    injected = LLMCache.__new__(LLMCache)
    injected.readonly = False
    assert _runner(cache=injected).cache is injected


def test_default_cache_is_built_when_none_injected() -> None:
    runner = _runner()
    assert isinstance(runner.cache, LLMCache)
    assert runner.cache.readonly is False


def test_on_scene_hook_fires_before_each_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    journal: list[str] = []
    scenes = [_RecordingScene(name="a", journal=journal), _RecordingScene(name="b", journal=journal)]
    monkeypatch.setattr(run_module, "SCENES", scenes)
    runner = _runner()
    runner.run(on_scene=lambda scene: journal.append(f"hook:{scene.name}"))
    assert journal == ["hook:a", "exec:a", "hook:b", "exec:b"]


def test_on_scene_hook_sees_the_scene_that_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(run_module, "SCENES", [_ExplodingScene(name="dies_here")])
    runner = _runner()
    with pytest.raises(RuntimeError, match="boom"):
        runner.run(on_scene=lambda scene: seen.append(scene.name))
    assert seen == ["dies_here"]


def test_run_without_hook_still_executes_all_scenes(monkeypatch: pytest.MonkeyPatch) -> None:
    journal: list[str] = []
    monkeypatch.setattr(run_module, "SCENES", [_RecordingScene(name="only", journal=journal)])
    _runner().run()
    assert journal == ["exec:only"]
