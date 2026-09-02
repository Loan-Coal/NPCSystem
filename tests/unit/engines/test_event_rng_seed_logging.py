"""
test_event_rng_seed_logging.py - Event sampling must record the seed it drew with.

Does NOT: touch Neo4j, the event pool file, or construct an EventHandler.

Dependencies injected: None; the seed resolver is a pure module function.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Iterator

from npc_engine.engines.events import event_handler as eh
from npc_engine.engines.events.event_handler import _rng_for_tick


def _captured_debug_logs() -> Iterator[list[str]]:
    """Capture on the module logger directly, not via caplog.

    utils/logging.py:83 sets propagate=False on the npc_engine logger, so once any
    earlier test in the session calls configure_logging(), root-based capture sees
    nothing and a caplog assertion passes or fails by test order. Same idiom as
    test_sev22_rng_determinism.py:80 and test_ollama_prompt_eval_logging.py:91.
    """
    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    handler = _Capture(level=logging.DEBUG)
    previous_level = eh.LOGGER.level
    eh.LOGGER.addHandler(handler)
    eh.LOGGER.setLevel(logging.DEBUG)
    try:
        yield captured
    finally:
        eh.LOGGER.removeHandler(handler)
        eh.LOGGER.setLevel(previous_level)


def test_configured_seed_is_logged() -> None:
    """A configured EVENT_RNG_SEED must be recorded, as gossip already records its own.

    npc-coding-principles makes seed logging strict for event sampling. Without it
    a surprising event draw cannot be replayed.
    """
    for captured in _captured_debug_logs():
        _rng_for_tick(configured=random.Random(42), seed=42, tick_id=7)

    logs = [m for m in captured if "event_sampling_rng" in m]
    assert logs, "expected an event_sampling_rng debug log line"
    assert "seed=42" in logs[0]


def test_tick_id_fallback_seed_is_logged() -> None:
    """With no configured seed the tick id is the seed, and that must be visible.

    `self._rng or random.Random(tick_id)` silently swapped between a global seed
    and a per-tick one and recorded neither, so a log reader could not tell which
    branch produced a draw.
    """
    for captured in _captured_debug_logs():
        _rng_for_tick(configured=None, seed=None, tick_id=7)

    logs = [m for m in captured if "event_sampling_rng" in m]
    assert logs, "expected an event_sampling_rng debug log line"
    assert "seed=7" in logs[0]


def test_configured_rng_is_returned_unchanged() -> None:
    """Logging must not disturb the RNG stream: the configured instance is reused."""
    configured = random.Random(42)

    assert _rng_for_tick(configured=configured, seed=42, tick_id=7) is configured


def test_fallback_rng_is_seeded_from_the_tick() -> None:
    """The fallback must stay reproducible per tick."""
    drawn = _rng_for_tick(configured=None, seed=None, tick_id=7).random()

    assert drawn == random.Random(7).random()
