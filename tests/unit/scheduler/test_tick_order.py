"""
test_tick_order.py - Pins the engine execution order (L13-10, SEV-15).

Guards two kinds of ordering invariant:

(a) One full-sequence test records the actual engine call order from a single
    tick and asserts it against an explicit literal list. Any reorder — even a
    legitimate one — is an immediate red. When a deliberate reorder is made,
    update _EXPECTED_SEQUENCE here and verify the pairwise tests in (b) still hold.
    The failure message points at docs/ENGINES.md where the order is documented.

(b) Ten pairwise tests cover each confirmed read-after-write dependency from
    L13.md §A.2. Two pairs are intentionally absent:
    - mood_contagion reads co-location from routine — engine deleted by T4.1.
    - faction_politics reads :Event rows from gossip/event — deleted by T3.2.
    Pairwise tests survive a legitimate reorder of unrelated engines.

Does NOT: open Neo4j, call an LLM, or perform real graph I/O.
Dependencies mocked: get_world_state, persist_clock_state, is_tick_done,
                     mark_tick_done; all via unittest.mock.patch.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.scheduler.game_clock import GameClock
from npc_engine.scheduler.tick_scheduler import TickScheduler
from npc_engine.world.time_utils import TimePoint
from npc_engine.world.world_state import WorldState

# ---------------------------------------------------------------------------
# Recording stubs
# ---------------------------------------------------------------------------

_WORLD = WorldState()


class _RecordingEngine:
    """TickEngine stub that appends its name to a shared call log."""

    def __init__(self, name: str, log: list[str]) -> None:
        """Initialise with canonical engine name and shared log reference."""
        self._name = name
        self._log = log

    async def run_tick(self, *, tick_id: int) -> dict[str, Any]:
        """Record this engine's invocation and return an empty result."""
        self._log.append(self._name)
        return {}


class _RecordingRoutineEngine:
    """RoutineTickEngine stub that records its invocation."""

    def __init__(self, log: list[str]) -> None:
        """Initialise with shared log reference."""
        self._log = log

    async def run_tick(self, *, time_of_day: str, tick_id: int) -> dict[str, Any]:
        """Record routine's invocation and return a minimal moved-zero result."""
        self._log.append("routine")
        return {"moved": 0}


class _RecordingConsolidationEngine:
    """ConsolidationTickEngine stub that records its invocation."""

    def __init__(self, log: list[str]) -> None:
        """Initialise with shared log reference."""
        self._log = log

    async def run_tick(self, *, game_time: TimePoint) -> dict[str, Any]:
        """Record memory_consolidation's invocation and return an empty result."""
        self._log.append("memory_consolidation")
        return {"consolidated": []}


# ---------------------------------------------------------------------------
# Shared helper — builds a fully-wired scheduler and runs one tick
# ---------------------------------------------------------------------------

async def _run_one_tick() -> list[str]:
    """Build a TickScheduler with recording stubs and advance exactly one tick.

    Gossip/event intervals are 1 so both fire on tick 1.
    Chapter interval is 1 and skip_llm_engines is False so chapter fires.
    Memory consolidation fires (advance_count=1, interval=1, 1%1==0).

    Returns:
        Ordered list of engine names in the sequence they were called.
    """
    log: list[str] = []

    def _eng(name: str) -> _RecordingEngine:
        return _RecordingEngine(name, log)

    scheduler = TickScheduler(
        clock=GameClock(mode="game_driven"),
        gossip_handler=_eng("gossip"),
        event_handler=_eng("event"),
        gossip_interval=1,
        event_interval=1,
        story_pacing_engine=_eng("story_pacing"),
        routine_engine=_RecordingRoutineEngine(log),
        chapter_engine=_eng("chapter"),
        chapter_interval=1,
        agenda_engine=_eng("agenda"),
        need_decay_engine=_eng("need_decay"),
        event_quest_trigger=_eng("event_quest"),
        need_quest_trigger=_eng("need_quest"),
        world_state_quest_trigger=_eng("world_state_quest"),
        proactive_dialogue_engine=_eng("proactive_dialogue"),
        reputation_engine=_eng("reputation"),
        intent_formation_engine=_eng("intent_formation"),
        goal_formation_engine=_eng("goal_formation"),
        player_model_engine=_eng("player_model"),
        director_engine=_eng("director"),
        memory_decay_engine=_eng("memory_decay"),
        scheme_advance_engine=_eng("scheme_advance"),
        scheme_detection_engine=_eng("scheme_detection"),
        memory_consolidation_engine=_RecordingConsolidationEngine(log),
        consolidation_advance_interval=1,
        distributed_lease_enabled=False,
    )

    with (
        patch(
            "npc_engine.scheduler.tick_scheduler.get_world_state",
            new=AsyncMock(return_value=_WORLD),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.persist_clock_state",
            new=AsyncMock(),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.is_tick_done",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.mark_tick_done",
            new=AsyncMock(),
        ),
    ):
        await scheduler.advance(session=AsyncMock(), tick_delta=1, time_delta_seconds=60)

    return log


# ---------------------------------------------------------------------------
# (a) Full execution-sequence pin
# ---------------------------------------------------------------------------

# IMPORTANT: this literal is intentionally NOT imported from tick_scheduler.py.
# Importing the sequence from the thing being tested makes the assertion circular.
# To update this after a deliberate reorder: change both _ordered_tick_engines()
# and this list, then re-run the pairwise tests in section (b) to confirm every
# read-after-write constraint still holds.
# See: docs/ENGINES.md §"The tick model" for the rationale for each position.
_EXPECTED_SEQUENCE: list[str] = [
    "story_pacing",
    "gossip",
    "event",
    "routine",
    "chapter",
    "agenda",
    "need_decay",
    "event_quest",
    "need_quest",
    "world_state_quest",
    "proactive_dialogue",
    "reputation",
    "intent_formation",
    "goal_formation",
    "player_model",
    "director",
    "memory_decay",
    "scheme_advance",
    "scheme_detection",
    "memory_consolidation",
]


@pytest.mark.asyncio
async def test_engine_execution_sequence() -> None:
    """Full tick execution order must match the expected literal sequence exactly.

    This test intentionally breaks on ANY reorder, including a deliberate one.
    If you reorder engines: update _EXPECTED_SEQUENCE above, then verify that
    every pairwise dependency test in the section below still passes.

    Failure here does NOT necessarily mean a bug — it may mean a legitimate
    reorder that requires updating two things: the source list and this literal.
    """
    actual = await _run_one_tick()
    assert actual == _EXPECTED_SEQUENCE, (
        f"\nActual:   {actual!r}"
        f"\nExpected: {_EXPECTED_SEQUENCE!r}"
        "\n\nEngine execution order has changed. If intentional, update "
        "_EXPECTED_SEQUENCE in this file and re-check pairwise tests below. "
        "See docs/ENGINES.md §'The tick model' for the documented order."
    )


# ---------------------------------------------------------------------------
# (b) Pairwise read-after-write dependency tests — L13.md §A.2, 10 active pairs
# ---------------------------------------------------------------------------

def _pos(log: list[str], name: str) -> int:
    """Return the first index of *name* in *log*, failing if absent."""
    try:
        return log.index(name)
    except ValueError:
        raise AssertionError(
            f"Engine '{name}' was not observed in the tick execution log: {log}"
        ) from None


@pytest.mark.asyncio
async def test_event_reads_after_story_pacing() -> None:
    """event reads WorldState.max_event_severity written this tick by story_pacing."""
    log = await _run_one_tick()
    assert _pos(log, "story_pacing") < _pos(log, "event"), (
        "story_pacing must run before event (L13.A.2 row 1)"
    )


@pytest.mark.asyncio
async def test_quest_triggers_read_after_story_pacing() -> None:
    """event_quest/need_quest/world_state_quest read WorldState.quest_generation_rate from story_pacing."""
    log = await _run_one_tick()
    sp = _pos(log, "story_pacing")
    assert sp < _pos(log, "event_quest"), (
        "event_quest must run after story_pacing (L13.A.2 row 2)"
    )
    assert sp < _pos(log, "need_quest"), (
        "need_quest must run after story_pacing (L13.A.2 row 2)"
    )
    assert sp < _pos(log, "world_state_quest"), (
        "world_state_quest must run after story_pacing (L13.A.2 row 2)"
    )


@pytest.mark.asyncio
async def test_need_decay_reads_after_routine() -> None:
    """need_decay reads (c)-[:LOCATED_AT]->(loc) written this tick by routine."""
    log = await _run_one_tick()
    assert _pos(log, "routine") < _pos(log, "need_decay"), (
        "routine must run before need_decay (L13.A.2 row 3)"
    )


@pytest.mark.asyncio
async def test_proactive_dialogue_reads_after_routine() -> None:
    """proactive_dialogue reads co-location written this tick by routine."""
    log = await _run_one_tick()
    assert _pos(log, "routine") < _pos(log, "proactive_dialogue"), (
        "routine must run before proactive_dialogue (L13.A.2 row 5)"
    )


@pytest.mark.asyncio
async def test_player_model_reads_after_routine() -> None:
    """player_model reads NPC+player co-location written this tick by routine."""
    log = await _run_one_tick()
    assert _pos(log, "routine") < _pos(log, "player_model"), (
        "routine must run before player_model (L13.A.2 row 6)"
    )


@pytest.mark.asyncio
async def test_event_quest_reads_after_event() -> None:
    """event_quest reads unprocessed :Event rows with no CAUSED_BY, written by event."""
    log = await _run_one_tick()
    assert _pos(log, "event") < _pos(log, "event_quest"), (
        "event must run before event_quest (L13.A.2 row 8)"
    )


@pytest.mark.asyncio
async def test_need_quest_reads_after_need_decay() -> None:
    """need_quest reads :Need.level below threshold, which need_decay updates this tick."""
    log = await _run_one_tick()
    assert _pos(log, "need_decay") < _pos(log, "need_quest"), (
        "need_decay must run before need_quest (L13.A.2 row 9)"
    )


@pytest.mark.asyncio
async def test_chapter_reads_after_gossip_and_event() -> None:
    """chapter reads recent :Event + completed :Quest written this tick by gossip and event."""
    log = await _run_one_tick()
    assert _pos(log, "gossip") < _pos(log, "chapter"), (
        "gossip must run before chapter (L13.A.2 row 10)"
    )
    assert _pos(log, "event") < _pos(log, "chapter"), (
        "event must run before chapter (L13.A.2 row 10)"
    )


@pytest.mark.asyncio
async def test_reputation_reads_after_gossip() -> None:
    """reputation reads RELATES_TO trust deltas written this tick by gossip."""
    log = await _run_one_tick()
    assert _pos(log, "gossip") < _pos(log, "reputation"), (
        "gossip must run before reputation (L13.A.2 row 11)"
    )


@pytest.mark.asyncio
async def test_scheme_detection_reads_after_scheme_advance() -> None:
    """scheme_detection reads covert :Event steps written this tick by scheme_advance."""
    log = await _run_one_tick()
    assert _pos(log, "scheme_advance") < _pos(log, "scheme_detection"), (
        "scheme_advance must run before scheme_detection (L13.A.2 row 12)"
    )
