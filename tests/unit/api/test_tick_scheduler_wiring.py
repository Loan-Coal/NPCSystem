"""
test_tick_scheduler_wiring.py - Guards the TickScheduler composition root (R3.4).

Does NOT: run a tick, or touch Neo4j/LLM infrastructure; the factories build
lazily and open no connections.

Dependencies injected: None; exercises the real DI factory.
"""

from __future__ import annotations

import pytest

from npc_engine.api.dependencies_engines import (
    TICK_SCHEDULER_ENGINE_SLOTS,
    EngineWiringError,
    _assert_every_engine_slot_wired,
    get_tick_scheduler,
)


def test_composition_root_wires_the_memory_consolidation_engine() -> None:
    """The tick path must actually run consolidation (R3.4a).

    get_memory_consolidation_engine() existed and TickScheduler accepted the slot,
    but the factory never passed it, so _maybe_consolidate_memory short-circuited
    on `is None` for every tick and the API reported consolidation: [] forever.
    """
    scheduler = get_tick_scheduler()

    assert scheduler._memory_consolidation_engine is not None


def test_composition_root_leaves_no_engine_slot_unwired() -> None:
    """The general form of the bug above: a None slot is a silent no-op.

    TickScheduler types 26 of its 28 engine slots Optional so tests can wire a
    subset. That is right for the class and wrong for the composition root, which
    is responsible for filling every one of them.
    """
    scheduler = get_tick_scheduler()

    unwired = [name for name in TICK_SCHEDULER_ENGINE_SLOTS if getattr(scheduler, f"_{name}") is None]

    assert unwired == []


def test_unwired_slot_is_rejected() -> None:
    """The guard names the offending slots rather than failing opaquely."""
    with pytest.raises(EngineWiringError) as caught:
        _assert_every_engine_slot_wired(
            {"gossip_handler": object(), "chapter_engine": None},
            expected=frozenset({"gossip_handler", "chapter_engine"}),
        )

    assert "chapter_engine" in caught.value.slots


def test_fully_wired_kwargs_are_accepted() -> None:
    """The happy path stays silent and returns nothing."""
    result = _assert_every_engine_slot_wired(
        {"gossip_handler": object(), "chapter_engine": object()},
        expected=frozenset({"gossip_handler", "chapter_engine"}),
    )

    assert result is None


def test_missing_slot_is_rejected_like_an_explicit_none() -> None:
    """An absent key is as unwired as a key set to None.

    The composition root builds its kwargs by dict merge, so a forgotten entry
    shows up as a missing key rather than a None value.
    """
    with pytest.raises(EngineWiringError) as caught:
        _assert_every_engine_slot_wired(
            {"gossip_handler": object()},
            expected=frozenset({"gossip_handler", "chapter_engine"}),
        )

    assert caught.value.slots == ("chapter_engine",)
