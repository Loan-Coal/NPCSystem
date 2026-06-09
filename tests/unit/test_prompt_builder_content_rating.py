"""
Tests for content-rating injection in build_system_prompt() (S16.3).

All pure unit tests — no I/O beyond loading the real YAML files.
"""
from __future__ import annotations

from npc_engine.engines.dialogue.prompt_builder import build_system_prompt

_CEILING_MARKER = "CONTENT CEILING"


def test_mature_rating_injects_no_rule() -> None:
    prompt = build_system_prompt(content_rating="mature")
    assert _CEILING_MARKER not in prompt


def test_everyone_rating_injects_rule() -> None:
    prompt = build_system_prompt(content_rating="everyone")
    assert _CEILING_MARKER in prompt


def test_rule_injected_once() -> None:
    prompt = build_system_prompt(content_rating="everyone")
    assert prompt.count(_CEILING_MARKER) == 1
