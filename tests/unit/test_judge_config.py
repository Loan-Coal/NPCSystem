"""
test_judge_config.py — Unit tests for the judge model-separation invariant.

Covers (evals/judge_config.py):
- default judge model is mixtral:8x7b (different family from qwen2.5 generation)
- exact collision (judge == a generation model) raises JudgeModelCollisionError
- same-family judge (qwen2.5:7b vs qwen2.5:14b) warns loudly but does NOT raise
- different-family judge resolves cleanly
- discover_generation_models() reads the real engine llm_config.yaml files
- JUDGE_MODEL env override is honored
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

# evals/ is on pytest's pythonpath via pyproject.
import judge_config
from judge_config import (
    DEFAULT_JUDGE_MODEL,
    JudgeModelCollisionError,
    discover_generation_models,
    resolve_judge_model,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_default_judge_model_is_mixtral() -> None:
    """With no env and a qwen-only generation set, the judge defaults to mixtral:8x7b."""
    assert DEFAULT_JUDGE_MODEL == "mixtral:8x7b"
    resolved = resolve_judge_model(requested=None, generation_models=("qwen2.5:14b",))
    assert resolved == "mixtral:8x7b"


def test_exact_collision_raises_and_names_both() -> None:
    """A judge equal to a generation model is a hard failure that names both models."""
    with pytest.raises(JudgeModelCollisionError) as exc:
        resolve_judge_model(requested="qwen2.5:14b", generation_models=("qwen2.5:14b",))
    msg = str(exc.value)
    assert "qwen2.5:14b" in msg


def test_same_family_warns_but_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    """A same-family judge (qwen2.5:7b vs qwen2.5:14b) warns but is allowed."""
    with caplog.at_level(logging.WARNING):
        resolved = resolve_judge_model(
            requested="qwen2.5:7b", generation_models=("qwen2.5:14b",)
        )
    assert resolved == "qwen2.5:7b"
    assert any("family" in rec.message.lower() for rec in caplog.records)


def test_different_family_is_clean(caplog: pytest.LogCaptureFixture) -> None:
    """A different-family judge resolves without warning or error."""
    with caplog.at_level(logging.WARNING):
        resolved = resolve_judge_model(
            requested="mixtral:8x7b", generation_models=("qwen2.5:14b",)
        )
    assert resolved == "mixtral:8x7b"
    assert not any("family" in rec.message.lower() for rec in caplog.records)


def test_discover_generation_models_reads_real_configs() -> None:
    """The real engine llm_config.yaml files declare exactly qwen2.5:14b (DEC-142)."""
    models = discover_generation_models(repo_root=_REPO_ROOT)
    assert models == ("qwen2.5:14b",)


def test_env_override_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    """JUDGE_MODEL env overrides the default when no explicit request is passed."""
    monkeypatch.setenv("JUDGE_MODEL", "llama3")
    resolved = resolve_judge_model(generation_models=("qwen2.5:14b",))
    assert resolved == "llama3"
