"""
test_sev19_prompt_redaction.py - Regression tests for env-gated LLM prompt logging.

Does NOT: instantiate Settings or perform I/O.

Dependencies injected: None.
"""

from __future__ import annotations

import pytest

from npc_engine.engines.dialogue.dialogue_handler import resolve_log_prompts


class _FakeSettings:
    """Minimal settings stub for resolve_log_prompts tests."""

    def __init__(self, log_llm_prompts: bool, env: str) -> None:
        self.LOG_LLM_PROMPTS = log_llm_prompts
        self.ENV = env


def test_resolve_log_prompts_true_only_in_dev() -> None:
    """resolve_log_prompts returns True only when both flag is set and ENV is dev."""
    settings = _FakeSettings(log_llm_prompts=True, env="dev")
    assert resolve_log_prompts(settings) is True


def test_resolve_log_prompts_false_in_staging() -> None:
    """resolve_log_prompts returns False when ENV is staging even if flag is True."""
    settings = _FakeSettings(log_llm_prompts=True, env="staging")
    assert resolve_log_prompts(settings) is False


def test_resolve_log_prompts_false_in_prod() -> None:
    """resolve_log_prompts returns False when ENV is prod even if flag is True."""
    settings = _FakeSettings(log_llm_prompts=True, env="prod")
    assert resolve_log_prompts(settings) is False


def test_resolve_log_prompts_false_when_flag_off() -> None:
    """resolve_log_prompts returns False when LOG_LLM_PROMPTS is False in dev."""
    settings = _FakeSettings(log_llm_prompts=False, env="dev")
    assert resolve_log_prompts(settings) is False
