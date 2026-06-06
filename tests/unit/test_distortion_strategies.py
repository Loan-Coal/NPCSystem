"""
test_distortion_strategies.py — Unit tests for the prefix-based distortion strategy callables.

Verifies that exaggeration, role_swap, and timeline_shift read their prefix
from the YAML loader rather than a hardcoded constant.

Does NOT: perform graph I/O, call LLMs, or write files.
Dependencies injected: None.
"""

from __future__ import annotations

from npc_engine.engines.gossip.strategies.exaggeration import exaggeration
from npc_engine.engines.gossip.strategies.prefix_loader import get_distortion_prefix
from npc_engine.engines.gossip.strategies.role_swap import role_swap
from npc_engine.engines.gossip.strategies.timeline_shift import timeline_shift


_SAMPLE = "troops marched north"


def test_exaggeration_uses_yaml_prefix() -> None:
    result = exaggeration(_SAMPLE)
    assert result.startswith(get_distortion_prefix("exaggeration"))


def test_exaggeration_appends_summary() -> None:
    result = exaggeration(_SAMPLE)
    assert result.endswith(_SAMPLE)


def test_role_swap_uses_yaml_prefix() -> None:
    result = role_swap(_SAMPLE)
    assert result.startswith(get_distortion_prefix("role_swap"))


def test_role_swap_appends_summary() -> None:
    result = role_swap(_SAMPLE)
    assert result.endswith(_SAMPLE)


def test_timeline_shift_uses_yaml_prefix() -> None:
    result = timeline_shift(_SAMPLE)
    assert result.startswith(get_distortion_prefix("timeline_shift"))


def test_timeline_shift_appends_summary() -> None:
    result = timeline_shift(_SAMPLE)
    assert result.endswith(_SAMPLE)
