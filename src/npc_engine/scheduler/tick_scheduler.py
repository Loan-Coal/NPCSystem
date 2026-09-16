"""
tick_scheduler.py - Coordinates game clock and tick execution for engines.
Layer: engines
Purpose: Coordinates the game clock and runs the registered tick-driven engines in a fixed
         order on each clock advance, isolating per-engine failures so one error never
         halts the tick.

Does NOT: define gossip/event/routine engine internals.

Dependencies injected: GameClock, GossipHandler, EventHandler, RoutineEngine,
                       MemoryConsolidationEngine (optional), EngineStatusStore (optional).
Used by: api.dependency_singletons (singleton), api.routes.clock.

Line-count note: This orchestrator coordinates 28 independent tick engines.
Splitting the advance() loop would create artificial coupling. See DEC-042.
"""

# DEC-042 exception: this file intentionally exceeds the 300-line limit because
# extracting per-engine blocks into a separate module would fragment a cohesive
# sequential orchestration that has no natural seam. See DECISIONS.md.

from __future__ import annotations

from typing import Any
import asyncio
import logging
from collections.abc import Awaitable, Callable

from neo4j import AsyncSession

from npc_engine.engines.base_engine import ConsolidationTickEngine, RoutineTickEngine, TickEngine
from npc_engine.graph.scheduling.tick_scheduler_queries import is_tick_done, mark_tick_done
from npc_engine.scheduler.engine_status_store import EngineStatusStore
from npc_engine.scheduler.engine_tick_timer import EngineTickTimer
from npc_engine.scheduler.game_clock import ClockState, GameClock
from npc_engine.scheduler.tick_lease import TickLeaseRepository, TickLeaseRepositoryProtocol
from npc_engine.world.time_utils import TimePoint
from npc_engine.world.world_state import WorldState
from npc_engine.config import get_settings
from npc_engine.graph.world_state.world_state_reader import get_world_state
from npc_engine.graph.world_state.world_state_writer import persist_clock_state


LOGGER = logging.getLogger(__name__)


class TickScheduler:
    """Orchestrates conditional gossip, event, and routine ticks."""

    def __init__(
        self,
        clock: GameClock,
        gossip_handler: TickEngine,
        event_handler: TickEngine,
        gossip_interval: int,
        event_interval: int,
        *,
        routine_engine: RoutineTickEngine | None = None,
        faction_politics_engine: TickEngine | None = None,
        story_pacing_engine: TickEngine | None = None,
        memory_consolidation_engine: ConsolidationTickEngine | None = None,
        clique_formation_engine: TickEngine | None = None,
        skill_progression_engine: TickEngine | None = None,
        treaty_engine: TickEngine | None = None,
        mood_contagion_engine: TickEngine | None = None,
        chapter_engine: TickEngine | None = None,
        agenda_engine: TickEngine | None = None,
        need_decay_engine: TickEngine | None = None,
        event_quest_trigger: TickEngine | None = None,
        need_quest_trigger: TickEngine | None = None,
        world_state_quest_trigger: TickEngine | None = None,
        proactive_dialogue_engine: TickEngine | None = None,
        reputation_engine: TickEngine | None = None,
        intent_formation_engine: TickEngine | None = None,
        goal_formation_engine: TickEngine | None = None,
        player_model_engine: TickEngine | None = None,
        director_engine: TickEngine | None = None,
        memory_decay_engine: TickEngine | None = None,
        scheme_advance_engine: TickEngine | None = None,
        scheme_detection_engine: TickEngine | None = None,
        consolidation_advance_interval: int = 1,
        chapter_interval: int = 1,
        distributed_lease_enabled: bool = False,
        scheduler_id: str = "main",
        lease_owner_id: str = "worker",
        lease_ttl_seconds: int = 30,
        lease_repo: TickLeaseRepositoryProtocol | None = None,
        engine_status_store: EngineStatusStore | None = None,
    ) -> None:
        """Initialise the tick scheduler.

        Args:
            clock: GameClock instance tracking tick and game-time progress.
            gossip_handler: Engine exposing ``run_tick(tick_id)``; called every
                ``gossip_interval`` ticks.
            event_handler: Engine exposing ``run_tick(tick_id)``; called every
                ``event_interval`` ticks.
            gossip_interval: Run gossip every N ticks; clamped to a minimum of 1.
            event_interval: Run events every N ticks; clamped to a minimum of 1.
            routine_engine: Optional engine exposing ``run_tick(time_of_day, tick_id)``
                called every tick to move characters per their schedules.
            faction_politics_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick to adjust faction standings from events and apply decay.
            story_pacing_engine: Optional engine exposing ``run_tick(tick_id)``
                called before gossip/event sampling to write pacing multipliers to WorldState.
            memory_consolidation_engine: Optional engine exposing ``run_tick(game_time)``
                called once per advance on the configured cadence.
            clique_formation_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; self-skips when the configured interval is not met.
            skill_progression_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; awards XP to characters for completed quests.
            treaty_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; expires treaties and checks mechanical conditions.
            mood_contagion_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; blends mood states between co-located affectionate NPCs.
            chapter_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; detects chapter transitions and labels them via LLM.
            agenda_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; resolves open agendas whose deadline has passed.
            need_decay_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; decays character need levels and applies location restoration.
            event_quest_trigger: Optional engine exposing ``run_tick(tick_id)``
                called every tick; generates draft quests from unprocessed trigger events.
            need_quest_trigger: Optional engine exposing ``run_tick(tick_id)``
                called every tick; generates draft quests for NPCs with critically low needs.
            world_state_quest_trigger: Optional engine exposing ``run_tick(tick_id)``
                called every tick; generates draft quests driven by the current world-state epoch.
            proactive_dialogue_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; checks co-located NPCs/players and emits proactive lines.
            reputation_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; propagates 1-hop personal reputation through the social graph.
            intent_formation_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; scores and enqueues proactive dialogue intents (Phase 14).
            player_model_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; updates each co-located NPC's model of the player (F1.4).
            director_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; evaluates the drama director decide() on idle/plateau
                signals and emits a beat via the events engine when a decision fires (F1.5).
            memory_decay_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; self-gates on its interval to apply charge-weighted
                vividness decay so low-salience memories fade over ticks (F1.7).
            scheme_advance_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; self-gates on its interval to advance active schemes
                by minting a covert Event per step (F1.6 / DEC-107 Option A).
            scheme_detection_engine: Optional engine exposing ``run_tick(tick_id)``
                called every tick; self-gates on its interval to discover witnessed,
                sufficiently-advanced schemes (status active→discovered) (F1.6).
            consolidation_advance_interval: Run consolidation every N advances; clamped to 1.
            chapter_interval: Run chapter engine every N ticks; clamped to 1. Default 1 preserves
                existing every-tick behavior; raise to reduce LLM call frequency.
            distributed_lease_enabled: When True, use ``lease_repo`` for cross-worker
                tick deduplication instead of the local SchedulerState Cypher queries.
            scheduler_id: Unique identifier for the scheduler node in Neo4j.
            lease_owner_id: Worker identifier passed to the lease repository.
            lease_ttl_seconds: Lease TTL passed to the lease repository; clamped to 1.
            lease_repo: Optional pre-built lease repository; constructed from
                ``scheduler_id``, ``lease_owner_id``, and ``lease_ttl_seconds`` when None.
            engine_status_store: Optional store for per-engine last-run tick and last error.
                When provided, all engine calls are tracked; errors are recorded without
                killing the loop.
        """

        self._clock = clock
        self._gossip_handler = gossip_handler
        self._event_handler = event_handler
        self._routine_engine = routine_engine
        self._faction_politics_engine = faction_politics_engine
        self._story_pacing_engine = story_pacing_engine
        self._memory_consolidation_engine = memory_consolidation_engine
        self._clique_formation_engine = clique_formation_engine
        self._skill_progression_engine = skill_progression_engine
        self._treaty_engine = treaty_engine
        self._mood_contagion_engine = mood_contagion_engine
        self._chapter_engine = chapter_engine
        self._agenda_engine = agenda_engine
        self._need_decay_engine = need_decay_engine
        self._event_quest_trigger = event_quest_trigger
        self._need_quest_trigger = need_quest_trigger
        self._world_state_quest_trigger = world_state_quest_trigger
        self._proactive_dialogue_engine = proactive_dialogue_engine
        self._reputation_engine = reputation_engine
        self._intent_formation_engine = intent_formation_engine
        self._goal_formation_engine = goal_formation_engine
        self._player_model_engine = player_model_engine
        self._director_engine = director_engine
        self._memory_decay_engine = memory_decay_engine
        self._scheme_advance_engine = scheme_advance_engine
        self._scheme_detection_engine = scheme_detection_engine
        self._consolidation_advance_interval = max(1, consolidation_advance_interval)
        self._chapter_interval = max(1, chapter_interval)
        self._advance_count = 0
        self._gossip_interval = max(1, gossip_interval)
        self._event_interval = max(1, event_interval)
        self._lock = asyncio.Lock()
        self._scheduler_id = scheduler_id
        self._distributed_lease_enabled = distributed_lease_enabled
        self._lease_ttl_seconds = max(1, lease_ttl_seconds)
        self._lease_repo = lease_repo or TickLeaseRepository(
            scheduler_id=scheduler_id,
            owner_id=lease_owner_id,
            lease_ttl_seconds=lease_ttl_seconds,
        )
        self._engine_status_store = engine_status_store

    async def _run_engine_safe(
        self,
        engine_name: str,
        tick_id: int,
        coro: Awaitable[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Await a coroutine, recording success or failure in the status store.

        On exception: logs ``tick_engine_error``, records the error, and returns
        None so the caller can skip appending a result without killing the loop.

        Args:
            engine_name: Canonical engine key used for status tracking.
            tick_id: Current tick ID, attached to log and status records.
            coro: Awaitable produced by calling the engine's run_tick method.
        Returns:
            Engine result dict[str, Any], or None if the engine raised an exception.
        """
        timer = EngineTickTimer(
            engine_name=engine_name, tick_id=tick_id, status_store=self._engine_status_store
        )
        try:
            result = await coro
            timer.record_success()
            return result
        except Exception as exc:
            LOGGER.error(
                "tick_engine_error",
                extra={"engine": engine_name, "tick_id": tick_id, "error": str(exc)},
            )
            timer.record_error(str(exc))
            return None

    async def _run_with_lease_timeout(self, coro: Awaitable[dict[str, Any]]) -> dict[str, Any]:
        timeout_seconds = max(1.0, float(self._lease_ttl_seconds) - 1.0)
        return await asyncio.wait_for(coro, timeout=timeout_seconds)

    async def _is_tick_done(self, session: AsyncSession, key: str, tick_id: int) -> bool:
        """Return True when tick_id is already recorded as done for the given key.

        Args:
            session: Active Neo4j async session.
            key: Property key on the SchedulerState node (e.g. 'gossip_ticks').
            tick_id: Tick ID to look up.

        Returns:
            True if tick_id is in the completed list; False otherwise.
        """
        return await is_tick_done(session, scheduler_id=self._scheduler_id, key=key, tick_id=tick_id)

    async def _mark_tick_done(self, session: AsyncSession, key: str, tick_id: int) -> None:
        """Append tick_id to the SchedulerState node's completed list for key (idempotent).

        Args:
            session: Active Neo4j async session.
            key: Property key on the SchedulerState node.
            tick_id: Tick ID to record as done.
        """
        await mark_tick_done(session, scheduler_id=self._scheduler_id, key=key, tick_id=tick_id)

    async def _run_distributed_engine_tick(
        self,
        *,
        session: AsyncSession,
        engine: str,
        tick_id: int,
        runner: Callable[[], Awaitable[dict[str, Any]]],
    ) -> tuple[bool, dict[str, Any] | None]:
        claimed = await self._lease_repo.try_claim(session=session, engine=engine, tick_id=tick_id)
        if claimed:
            try:
                row = await self._run_with_lease_timeout(runner())
            except Exception as exc:
                await self._lease_repo.mark_failed(
                    session=session,
                    engine=engine,
                    tick_id=tick_id,
                    error=str(exc),
                )
                raise

            done = await self._lease_repo.mark_done(session=session, engine=engine, tick_id=tick_id)
            if not done and not await self._lease_repo.is_done(
                session=session,
                engine=engine,
                tick_id=tick_id,
            ):
                raise RuntimeError(f"failed to mark completed {engine} tick {tick_id}")
            return False, row

        unresolved = not await self._lease_repo.is_done(session=session, engine=engine, tick_id=tick_id)
        return unresolved, None

    def _build_empty_response(self) -> dict[str, Any]:
        """Return initial per-engine result dict[str, Any] with empty lists for all engine keys."""
        return {
            "clock": self._clock.state.model_dump(),
            "gossip": [],
            "event": [],
            "routine": [],
            "faction_politics": [],
            "story_pacing": [],
            "consolidation": [],
            "clique": [],
            "skill_progression": [],
            "treaty": [],
            "mood_contagion": [],
            "chapter": [],
            "agenda": [],
            "need_decay": [],
            "event_quest": [],
            "need_quest": [],
            "world_state_quest": [],
            "proactive_dialogue": [],
            "reputation": [],
            "intent_formation": [],
            "goal_formation": [],
            "player_model": [],
            "director": [],
            "memory_decay": [],
            "scheme_advance": [],
            "scheme_detection": [],
        }

    def _ordered_tick_engines(self) -> list[tuple[str, TickEngine | None]]:
        """Return (name, engine) pairs for all simple per-tick engines, in execution order."""
        return [
            ("faction_politics", self._faction_politics_engine),
            ("clique", self._clique_formation_engine),
            ("skill_progression", self._skill_progression_engine),
            ("treaty", self._treaty_engine),
            ("mood_contagion", self._mood_contagion_engine),
            ("agenda", self._agenda_engine),
            ("need_decay", self._need_decay_engine),
            ("event_quest", self._event_quest_trigger),
            ("need_quest", self._need_quest_trigger),
            ("world_state_quest", self._world_state_quest_trigger),
            ("proactive_dialogue", self._proactive_dialogue_engine),
            ("reputation", self._reputation_engine),
            ("intent_formation", self._intent_formation_engine),
            ("goal_formation", self._goal_formation_engine),
            ("player_model", self._player_model_engine),
            ("director", self._director_engine),
            ("memory_decay", self._memory_decay_engine),
            ("scheme_advance", self._scheme_advance_engine),
            ("scheme_detection", self._scheme_detection_engine),
        ]

    async def _run_distributed_interval(
        self,
        *,
        session: AsyncSession,
        name: str,
        tick_id: int,
        engine: TickEngine,
        response: dict[str, Any],
    ) -> bool:
        """Run one interval engine via distributed lease; return True if tick is unresolved."""
        timer = EngineTickTimer(
            engine_name=name, tick_id=tick_id, status_store=self._engine_status_store
        )
        try:
            unresolved, row = await self._run_distributed_engine_tick(
                session=session,
                engine=name,
                tick_id=tick_id,
                runner=lambda: engine.run_tick(tick_id=tick_id),
            )
        except Exception as exc:
            LOGGER.error("tick_engine_error", extra={"engine": name, "tick_id": tick_id, "error": str(exc)})
            timer.record_error(str(exc))
            return False
        else:
            # row is None when another scheduler held the lease: nothing ran here to time.
            if row is not None:
                timer.record_success()
        if row is not None:
            response[name].append(row)
        return unresolved

    async def _run_local_interval(
        self,
        *,
        session: AsyncSession,
        name: str,
        cypher_key: str,
        tick_id: int,
        engine: TickEngine,
        response: dict[str, Any],
    ) -> None:
        """Handle Cypher-state dedup for an interval engine; skips if already recorded done."""
        done = await self._is_tick_done(session=session, key=cypher_key, tick_id=tick_id)
        if not done:
            row = await self._run_engine_safe(name, tick_id, engine.run_tick(tick_id=tick_id))
            await self._mark_tick_done(session=session, key=cypher_key, tick_id=tick_id)
            if row is not None:
                response[name].append(row)

    async def _run_interval_engine(
        self,
        *,
        session: AsyncSession,
        name: str,
        cypher_key: str,
        tick_id: int,
        interval: int,
        engine: TickEngine,
        response: dict[str, Any],
    ) -> bool:
        """Run an interval engine (gossip/event) if tick is due; return True if unresolved."""
        if tick_id % interval != 0:
            return False
        if self._distributed_lease_enabled:
            return await self._run_distributed_interval(
                session=session, name=name, tick_id=tick_id,
                engine=engine, response=response,
            )
        await self._run_local_interval(
            session=session, name=name, cypher_key=cypher_key,
            tick_id=tick_id, engine=engine, response=response,
        )
        return False

    async def _run_tick_body(
        self, *, session: AsyncSession, tick_id: int,
        skip_llm_engines: bool, response: dict[str, Any], world_state: WorldState,
    ) -> bool:
        """Run all engines for one tick; return True if a distributed tick is unresolved."""
        if self._story_pacing_engine is not None:
            row = await self._run_engine_safe("story_pacing", tick_id, self._story_pacing_engine.run_tick(tick_id=tick_id))
            if row is not None:
                response["story_pacing"].append(row)
        gossip_unresolved = await self._run_interval_engine(
            session=session, name="gossip", cypher_key="gossip_ticks",
            tick_id=tick_id, interval=self._gossip_interval, engine=self._gossip_handler, response=response,
        )
        event_unresolved = await self._run_interval_engine(
            session=session, name="event", cypher_key="event_ticks",
            tick_id=tick_id, interval=self._event_interval, engine=self._event_handler, response=response,
        )
        if self._routine_engine is not None:
            row = await self._run_engine_safe("routine", tick_id, self._routine_engine.run_tick(time_of_day=world_state.time_of_day, tick_id=tick_id))
            if row is not None:
                response["routine"].append(row)
        if (not skip_llm_engines and self._chapter_engine is not None
                and tick_id % self._chapter_interval == 0):
            row = await self._run_engine_safe("chapter", tick_id, self._chapter_engine.run_tick(tick_id=tick_id))
            if row is not None:
                response["chapter"].append(row)
        for name, engine in self._ordered_tick_engines():
            if engine is not None:
                row = await self._run_engine_safe(name, tick_id, engine.run_tick(tick_id=tick_id))
                if row is not None:
                    response[name].append(row)
        return gossip_unresolved or event_unresolved

    async def _persist_clock(self, session: AsyncSession, *, tick_id: int, game_time_seconds: int) -> None:
        """Write the post-advance clock state onto the singleton WorldState node."""
        await persist_clock_state(
            session,
            world_id=get_settings().WORLD_ID,
            tick_id=tick_id,
            game_time_seconds=game_time_seconds,
        )

    async def _finalize_advance(
        self,
        *,
        session: AsyncSession,
        tick_delta: int,
        advanced_ticks: int,
        start_tick: int,
        skip_llm_engines: bool,
        world_state: WorldState,
        response: dict[str, Any],
        time_delta_seconds: int,
    ) -> None:
        """Persist and advance clock state, then conditionally run memory consolidation.

        Persists the new clock state to the graph BEFORE advancing the in-memory clock,
        so a failed persist leaves memory and graph consistent at the pre-advance tick
        rather than torn. On persist failure the exception propagates out of advance():
        the HTTP route returns 500 and TickAutopilot logs and retries next interval. The
        engines for the failed tick range have already run and will re-run on retry — the
        same replay window that already exists when advance() raises mid-loop, covered by
        the existing SchedulerState / tick-lease dedup for gossip and event (ISSUE-165).
        """
        advanced_seconds = 0 if tick_delta <= 0 else int((time_delta_seconds * advanced_ticks) / tick_delta)
        await self._persist_clock(
            session,
            tick_id=start_tick + advanced_ticks,
            game_time_seconds=self._clock.state.game_time_seconds + advanced_seconds,
        )
        state = await self._clock.advance(tick_delta=advanced_ticks, time_delta_seconds=advanced_seconds)
        response["clock"] = state.model_dump()
        self._advance_count += 1
        await self._maybe_consolidate_memory(
            skip_llm_engines=skip_llm_engines,
            consolidation_tick=start_tick + advanced_ticks,
            world_state=world_state,
            response=response,
        )

    async def _maybe_consolidate_memory(
        self,
        *,
        skip_llm_engines: bool,
        consolidation_tick: int,
        world_state: WorldState,
        response: dict[str, Any],
    ) -> None:
        """Run memory consolidation when this advance lands on the consolidation interval."""
        if (skip_llm_engines or self._memory_consolidation_engine is None
                or self._advance_count % self._consolidation_advance_interval != 0):
            return
        game_time = TimePoint(
            year=world_state.year,
            season=world_state.season,
            day=world_state.day,
            time_of_day=world_state.time_of_day,
        )
        consolidation_row = await self._run_engine_safe(
            "memory_consolidation", consolidation_tick,
            self._memory_consolidation_engine.run_tick(game_time=game_time),
        )
        response["consolidation"] = (
            consolidation_row.get("consolidated", []) if consolidation_row is not None else []
        )

    async def advance(self, session: AsyncSession, tick_delta: int, time_delta_seconds: int, skip_llm_engines: bool = False) -> dict[str, Any]:
        """Advance the clock and run due handlers, returning per-engine result lists.

        Iterates [current+1, current+tick_delta]. Engines run at configured intervals;
        gossip/event support distributed dedup. Per-engine exceptions are caught and
        do not stop the loop.

        Args:
            session: Active Neo4j async session.
            tick_delta: Ticks to advance; non-positive is a no-op.
            time_delta_seconds: In-game seconds advanced proportionally.
            skip_llm_engines: When True, skip chapter and consolidation engines.

        Returns:
            Dict with ``clock``, ``gossip``, ``event``, and per-engine result lists.
        """
        async with self._lock:
            start_tick = self._clock.state.tick_id
            end_tick = start_tick + max(0, tick_delta)
            response = self._build_empty_response()
            world_state = await get_world_state(session=session, world_id=get_settings().WORLD_ID)
            advanced_ticks = 0
            for tick_id in range(start_tick + 1, end_tick + 1):
                if await self._run_tick_body(
                    session=session, tick_id=tick_id,
                    skip_llm_engines=skip_llm_engines,
                    response=response, world_state=world_state,
                ):
                    break
                advanced_ticks += 1
            await self._finalize_advance(
                session=session, tick_delta=tick_delta, advanced_ticks=advanced_ticks,
                start_tick=start_tick, skip_llm_engines=skip_llm_engines,
                world_state=world_state, response=response,
                time_delta_seconds=time_delta_seconds,
            )
            return response

    @property
    def state(self) -> ClockState:
        """Return the current immutable clock state snapshot.

        Returns:
            ClockState from the underlying GameClock.
        """

        return self._clock.state

    @property
    def next_gossip_tick(self) -> int:
        """Return the next tick at which gossip will run.

        Returns:
            Tick ID of the next scheduled gossip execution.
        """

        tick = self._clock.state.tick_id
        return tick + (self._gossip_interval - (tick % self._gossip_interval))

    @property
    def next_event_tick(self) -> int:
        """Return the next tick at which event generation will run.

        Returns:
            Tick ID of the next scheduled event execution.
        """

        tick = self._clock.state.tick_id
        return tick + (self._event_interval - (tick % self._event_interval))

    @property
    def engine_status(self) -> dict[str, Any]:
        """Return a snapshot of per-engine status records as serialisable dicts.

        Returns:
            Dict mapping engine name to its status record fields, or {} when no
            engine_status_store was configured.
        """
        if self._engine_status_store is None:
            return {}
        return {
            name: record.model_dump()
            for name, record in self._engine_status_store.get_all().items()
        }
