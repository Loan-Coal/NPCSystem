"""
test_sev22_rng_determinism.py - Regression tests for SEV-22: seeded RNG on gossip/quest paths.

Verifies:
- _secret_rng_seed is a pure deterministic function.
- _quest_rng_seed is a pure deterministic function.
- Different inputs produce different seeds.
- Seed is logged (via patched LOGGER.debug).
"""

from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from npc_engine.engines.gossip.gossip_handler import _secret_rng_seed  # type: ignore[attr-defined]
from npc_engine.engines.quest_generation.quest_generation_engine import (
    _quest_rng_seed,  # type: ignore[attr-defined]
)


# ── _secret_rng_seed ──────────────────────────────────────────────────────────


def test_secret_rng_seed_is_deterministic() -> None:
    """Same inputs → same seed."""
    s1 = _secret_rng_seed("sharer1", "receiver1", 42)
    s2 = _secret_rng_seed("sharer1", "receiver1", 42)
    assert s1 == s2


def test_secret_rng_seed_different_tick_differs() -> None:
    """Different tick → different seed."""
    s1 = _secret_rng_seed("sharer1", "receiver1", 1)
    s2 = _secret_rng_seed("sharer1", "receiver1", 2)
    assert s1 != s2


def test_secret_rng_seed_different_pair_differs() -> None:
    """Different sharer → different seed."""
    s1 = _secret_rng_seed("sharer1", "receiver1", 1)
    s2 = _secret_rng_seed("sharer2", "receiver1", 1)
    assert s1 != s2


def test_secret_rng_seed_returns_int() -> None:
    assert isinstance(_secret_rng_seed("a", "b", 0), int)


# ── _quest_rng_seed ───────────────────────────────────────────────────────────


def test_quest_rng_seed_is_deterministic() -> None:
    """Same inputs → same seed."""
    s1 = _quest_rng_seed("npc_1", 10)
    s2 = _quest_rng_seed("npc_1", 10)
    assert s1 == s2


def test_quest_rng_seed_different_day_differs() -> None:
    """Different world day → different seed."""
    s1 = _quest_rng_seed("npc_1", 1)
    s2 = _quest_rng_seed("npc_1", 2)
    assert s1 != s2


def test_quest_rng_seed_returns_int() -> None:
    assert isinstance(_quest_rng_seed("npc_1", 0), int)


# ── Seed logged in gossip _run_side_effects ───────────────────────────────────


async def test_secret_propagation_logs_seed() -> None:
    """Driving the real secret-share path emits the per-pair RNG seed at DEBUG.

    Uses trust=0 (HOSTILE → share probability 0.0) so the rng check returns before any
    graph I/O — session is never touched. Captures on the engine logger directly (not
    caplog) because utils.logging sets propagate=False, so root-based capture sees
    nothing. Deleting the LOGGER.debug call breaks this test (closes the SEV-22/L4-02
    asserted-not-measured gap).
    """
    import logging

    from npc_engine.engines.gossip import gossip_handler as gh

    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    handler = gh.GossipHandler.__new__(gh.GossipHandler)
    expected_seed = gh._secret_rng_seed("sharer_x", "receiver_y", 99)
    cap = _Capture(level=logging.DEBUG)
    previous_level = gh.LOGGER.level
    gh.LOGGER.addHandler(cap)
    gh.LOGGER.setLevel(logging.DEBUG)
    try:
        await handler._maybe_propagate_secret(
            session=None,  # unused: HOSTILE early-returns before any graph call
            sharer_id="sharer_x",
            receiver_id="receiver_y",
            trust=0,
            tick_id=99,
        )
    finally:
        gh.LOGGER.removeHandler(cap)
        gh.LOGGER.setLevel(previous_level)

    seed_logs = [m for m in captured if "gossip_secret_rng" in m]
    assert seed_logs, "expected a gossip_secret_rng debug log line"
    assert f"seed={expected_seed}" in seed_logs[0]
