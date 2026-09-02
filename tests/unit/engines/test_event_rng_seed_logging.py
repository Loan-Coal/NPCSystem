"""
test_event_rng_seed_logging.py - Event sampling must record the seed it drew with.

Does NOT: touch Neo4j, the event pool file, or construct an EventHandler.

Dependencies injected: None; the seed resolver is a pure module function.
"""

from __future__ import annotations

import logging
import random

import pytest

from npc_engine.engines.events.event_handler import _rng_for_tick


def test_configured_seed_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """A configured EVENT_RNG_SEED must be recorded, as gossip already records its own.

    npc-coding-principles makes seed logging strict for event sampling. Without it
    a surprising event draw cannot be replayed.
    """
    configured = random.Random(42)

    with caplog.at_level(logging.DEBUG, logger="npc_engine.engines.events.event_handler"):
        _rng_for_tick(configured=configured, seed=42, tick_id=7)

    assert "event_sampling_rng" in caplog.text
    assert "seed=42" in caplog.text


def test_tick_id_fallback_seed_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """With no configured seed the tick id is the seed, and that must be visible.

    `self._rng or random.Random(tick_id)` silently swapped between a global seed
    and a per-tick one and recorded neither, so a log reader could not tell which
    branch produced a draw.
    """
    with caplog.at_level(logging.DEBUG, logger="npc_engine.engines.events.event_handler"):
        _rng_for_tick(configured=None, seed=None, tick_id=7)

    assert "event_sampling_rng" in caplog.text
    assert "seed=7" in caplog.text


def test_configured_rng_is_returned_unchanged() -> None:
    """Logging must not disturb the RNG stream: the configured instance is reused."""
    configured = random.Random(42)

    assert _rng_for_tick(configured=configured, seed=42, tick_id=7) is configured


def test_fallback_rng_is_seeded_from_the_tick() -> None:
    """The fallback must stay reproducible per tick."""
    drawn = _rng_for_tick(configured=None, seed=None, tick_id=7).random()

    assert drawn == random.Random(7).random()
