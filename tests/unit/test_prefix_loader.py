"""
test_prefix_loader.py — Unit tests for the distortion prefix YAML loader.

Does NOT: perform graph I/O, call LLMs, or write files.
Dependencies injected: None.
"""

from __future__ import annotations

import pytest

from npc_engine.engines.gossip.strategies.prefix_loader import get_distortion_prefix


def test_get_distortion_prefix_exaggeration() -> None:
    prefix = get_distortion_prefix("exaggeration")
    assert "catastrophic" in prefix.lower()


def test_get_distortion_prefix_role_swap() -> None:
    prefix = get_distortion_prefix("role_swap")
    assert isinstance(prefix, str)
    assert len(prefix) > 0


def test_get_distortion_prefix_timeline_shift() -> None:
    prefix = get_distortion_prefix("timeline_shift")
    assert isinstance(prefix, str)
    assert len(prefix) > 0


def test_get_distortion_prefix_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_distortion_prefix("nonexistent")


def test_get_distortion_prefix_returns_string() -> None:
    for key in ("exaggeration", "role_swap", "timeline_shift"):
        result = get_distortion_prefix(key)
        assert isinstance(result, str), f"expected str for key={key!r}, got {type(result)}"
