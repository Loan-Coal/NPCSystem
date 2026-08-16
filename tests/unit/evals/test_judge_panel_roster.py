"""
Module: test_judge_panel_roster
Layer: test (unit)
Purpose: Tests for evals/judge_config.py's judge-panel roster resolution
         (EVAL-P21.0) — the generation model must never be seated on the
         panel, and same-family seats must warn loudly, matching the
         single-judge collision/warning contract already enforced for
         resolve_judge_model.
Dependencies: pytest, judge_config (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

import logging

import pytest

from judge_config import (
    DEFAULT_PANEL_MODELS,
    JudgeModelCollisionError,
    resolve_judge_panel,
)

_GEN_MODELS = ("qwen2.5:7b",)


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_generation_model_cannot_be_seated_on_the_panel() -> None:
    """A panel seat equal to the generation model raises, exactly like a single judge."""
    with pytest.raises(JudgeModelCollisionError, match="qwen2.5:7b"):
        resolve_judge_panel(
            requested=("mixtral:8x7b", "qwen2.5:7b", "llama3.1:8b"),
            generation_models=_GEN_MODELS,
        )


# ---------------------------------------------------------------------------
# Behaviour tests
# ---------------------------------------------------------------------------


def test_default_panel_has_three_distinct_families() -> None:
    """The default roster (DEC-183) has one seat per family, none matching generation."""
    panel = resolve_judge_panel(generation_models=_GEN_MODELS)
    assert len(panel) == 3
    families = {m.split(":", 1)[0] for m in panel}
    assert len(families) == 3, f"expected 3 distinct families, got {families}"
    assert "qwen2.5" not in families or all(m != "qwen2.5:7b" for m in panel)


def test_default_panel_is_mixtral_qwen14b_llama() -> None:
    """Pins the roster chosen via AskUserQuestion (DEC-183)."""
    assert DEFAULT_PANEL_MODELS == ("mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b")


def test_same_family_seat_warns_but_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    """qwen2.5:14b is same-family as qwen2.5:7b (the generator) — allowed, but must warn."""
    with caplog.at_level(logging.WARNING, logger="judge_config"):
        panel = resolve_judge_panel(
            requested=("mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b"),
            generation_models=_GEN_MODELS,
        )
    assert panel == ("mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b")
    assert any("qwen2.5:14b" in record.message for record in caplog.records)


def test_requested_panel_overrides_default() -> None:
    """An explicit requested roster is used verbatim (subject to the collision check)."""
    panel = resolve_judge_panel(
        requested=("mixtral:8x7b", "gemma2:9b", "llama3.1:8b"),
        generation_models=_GEN_MODELS,
    )
    assert panel == ("mixtral:8x7b", "gemma2:9b", "llama3.1:8b")


def test_every_seat_checked_not_just_the_first() -> None:
    """A collision in the LAST seat must still raise — not just the first checked."""
    with pytest.raises(JudgeModelCollisionError, match="qwen2.5:7b"):
        resolve_judge_panel(
            requested=("mixtral:8x7b", "llama3.1:8b", "qwen2.5:7b"),
            generation_models=_GEN_MODELS,
        )
