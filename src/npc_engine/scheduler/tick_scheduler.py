"""
tick_scheduler.py - Coordinates game clock and tick execution for engines.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: define gossip/event/routine engine internals.

Dependencies injected: GameClock, GossipHandler, EventHandler, RoutineEngine,
                       MemoryConsolidationEngine (optional), EngineStatusStore (optional).
Used by: api.dependency_singletons (singleton), api.routes.clock.

Line-count note: This orchestrator coordinates 16 independent tick engines.
Splitting the advance() loop would create artificial coupling. See DEC-042.
"""

# DEC-042 exception: this file intentionally exceeds the 300-line limit because
# extracting per-engine blocks into a separate module would fragment a cohesive
# sequential orchestration that has no natural seam. See DECISIONS.md.

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from neo4j import AsyncSession

from npc_engine.engines.base_engine import BaseEngine
from npc_engine.scheduler.engine_status_store import EngineStatusStore
from npc_engine.scheduler.game_clock import ClockState, GameClock
from npc_engine.scheduler.tick_lease import TickLeaseRepository, TickLeaseRepositoryProtocol
from npc_engine.world.time_utils import TimePoint
from npc_engine.config import get_settings
from npc_engine.world.world_reader import get_world_state


LOGGER = logging.getLogger(__name__)


CYPHER_TICK_DONE = """
MERGE (s:SchedulerState {id: $scheduler_id})
WITH s, coalesce(s[$key], []) AS completed
RETURN $tick_id IN completed AS done
"""


CYPHER_MARK_TICK_DONE = """
MERGE (s:SchedulerState {id: $scheduler_id})
WITH s, coalesce(s[$key], []) AS completed
SET s[$key] = CASE
    WHEN $tick_id IN completed THEN completed
    ELSE completed + $tick_id
END
"""


class TickScheduler:
    """Orchestrates conditional gossip, event, and routine ticks."""

    def __init__(
        self,
        clock: GameClock,
        gossip_handler: BaseEngine,
        event_handler: BaseEngine,
        gossip_interval: int,
        event_interval: int,
        *,
        routine_engine: BaseEngine | None = None,
        faction_politics_engine: BaseEngine | None = None,
        story_pacing_engine: BaseEngine | None = None,
        memory_consolidation_engine: BaseEngine | None = None,
        clique_formation_engine: BaseEngine | None = None,
        skill_progression_engine: BaseEngine | None = None,
        oath_engine: BaseEngine | None = None,
        treaty_engine: BaseEngine | None = None,
        mood_contagion_engine: BaseEngine | None = None,
        chapter_engine: BaseEngine | None = None,
        succession_engine: BaseEngine | None = None,
        agenda_engine: BaseEngine | None = None,
        need_decay_engine: BaseEngine | None = None,
        military_engine: BaseEngine | None = None,
        event_quest_trigger: BaseEngine | None = None,
        need_quest_trigger: BaseEngine | None = None,
        world_state_quest_trigger: BaseEngine | None = None,
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
            gossip_handler: Engine exposing ``run_tick(session, tick_id)``; called every
                ``gossip_interval`` ticks.
            event_handler: Engine exposing ``run_tick(session, tick_id)``; called every
                ``event_interval`` ticks.
            gossip_interval: Run gossip every N ticks; clamped to a minimum of 1.
            event_interval: Run events every N ticks; clamped to a minimum of 1.
            routine_engine: Optional engine exposing ``run_tick(session, time_of_day, tick_id)``
                called every tick to move characters per their schedules.
            faction_politics_engine: Optional engine exposing ``run_tick(session)``
                called every tick to adjust faction standings from events and apply decay.
            story_pacing_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called before gossip/event sampling to write pacing multipliers to WorldState.
            memory_consolidation_engine: Optional engine exposing ``run_tick(session, game_time)``
                called once per advance on the configured cadence.
            clique_formation_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; self-skips when the configured interval is not met.
            skill_progression_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; awards XP to characters for completed quests.
            oath_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; expires pledges and runs stub violation checks.
            treaty_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; expires treaties and checks mechanical conditions.
            mood_contagion_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; blends mood states between co-located affectionate NPCs.
            chapter_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; detects chapter transitions and labels them via LLM.
            succession_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; grants vacant inheritable titles to the first eligible heir.
            agenda_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; resolves open agendas whose deadline has passed.
            need_decay_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; decays character need levels and applies location restoration.
            military_engine: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; currently a no-op stub (see ISSUES.md ISSUE-001).
            event_quest_trigger: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; generates draft quests from unprocessed trigger events.
            need_quest_trigger: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; generates draft quests for NPCs with critically low needs.
            world_state_quest_trigger: Optional engine exposing ``run_tick(session, tick_id)``
                called every tick; generates draft quests driven by the current world-state epoch.
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
        self._oath_engine = oath_engine
        self._treaty_engine = treaty_engine
        self._mood_contagion_engine = mood_contagion_engine
        self._chapter_engine = chapter_engine
        self._succession_engine = succession_engine
        self._agenda_engine = agenda_engine
        self._need_decay_engine = need_decay_engine
        self._military_engine = military_engine
        self._event_quest_trigger = event_quest_trigger
        self._need_quest_trigger = need_quest_trigger
        self._world_state_quest_trigger = world_state_quest_trigger
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
        coro: Awaitable[dict],
    ) -> dict | None:
        """Await a coroutine, recording success or failure in the status store.

        On exception: logs ``tick_engine_error``, records the error, and returns
        None so the caller can skip appending a result without killing the loop.

        Args:
            engine_name: Canonical engine key used for status tracking.
            tick_id: Current tick ID, attached to log and status records.
            coro: Awaitable produced by calling the engine's run_tick method.
        Returns:
            Engine result dict, or None if the engine raised an exception.
        """
        try:
            result = await coro
            if self._engine_status_store is not None:
                self._engine_status_store.record_success(engine_name, tick_id)
            return result
        except Exception as exc:
            LOGGER.error(
                "tick_engine_error",
                extra={"engine": engine_name, "tick_id": tick_id, "error": str(exc)},
            )
            if self._engine_status_store is not None:
                self._engine_status_store.record_error(engine_name, tick_id, str(exc))
            return None

    async def _run_with_lease_timeout(self, coro):
        timeout_seconds = max(1.0, float(self._lease_ttl_seconds) - 1.0)
        return await asyncio.wait_for(coro, timeout=timeout_seconds)

    async def _is_tick_done(self, session: AsyncSession, key: str, tick_id: int) -> bool:
        result = await session.run(
            CYPHER_TICK_DONE,
            scheduler_id=self._scheduler_id,
            key=key,
            tick_id=tick_id,
        )
        row = await result.single()
        return bool(row["done"]) if row is not None else False

    async def _mark_tick_done(self, session: AsyncSession, key: str, tick_id: int) -> None:
        await session.run(
            CYPHER_MARK_TICK_DONE,
            scheduler_id=self._scheduler_id,
            key=key,
            tick_id=tick_id,
        )

    async def _run_distributed_engine_tick(
        self,
        *,
        session: AsyncSession,
        engine: str,
        tick_id: int,
        runner: Callable[[], Awaitable[dict]],
    ) -> tuple[bool, dict | None]:
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

    async def advance(self, session: AsyncSession, tick_delta: int, time_delta_seconds: int, skip_llm_engines: bool = False) -> dict:
        """Advance the clock and run any handlers that are due at the resulting tick.

        Iterates each tick in ``[current+1, current+tick_delta]``. A tick is skipped
        for the relevant engine if it was already handled (via local state or distributed
        lease). When distributed leases are enabled and a tick is unresolved (claimed by
        another worker but not yet done), iteration stops early.

        Per-engine exceptions are caught, logged as ``tick_engine_error``, and recorded
        in the ``engine_status_store`` (when configured). The loop always continues to
        the next engine and the next tick regardless of individual failures.

        Args:
            session: Active Neo4j async session.
            tick_delta: Number of ticks to advance; non-positive values are no-ops for
                the clock but the method still returns the current state.
            time_delta_seconds: In-game seconds proportionally advanced alongside ticks.
            skip_llm_engines: When True, skip chapter and memory_consolidation engines
                regardless of their cadence. Used by the autopilot when the LLM budget
                for the current window is exhausted.

        Returns:
            Dict with ``clock`` (ClockState dump), ``gossip`` (list of gossip tick
            results), and ``event`` (list of event tick results).
        """

        async with self._lock:
            start_tick = self._clock.state.tick_id
            end_tick = start_tick + max(0, tick_delta)
            advanced_ticks = 0
            response: dict = {
                "clock": self._clock.state.model_dump(),
                "gossip": [],
                "event": [],
                "routine": [],
                "faction_politics": [],
                "story_pacing": [],
                "consolidation": [],
                "clique": [],
                "skill_progression": [],
                "oath": [],
                "treaty": [],
                "mood_contagion": [],
                "chapter": [],
                "succession": [],
                "agenda": [],
                "need_decay": [],
                "military": [],
                "event_quest": [],
                "need_quest": [],
                "world_state_quest": [],
            }
            world_state = await get_world_state(session=session, world_id=get_settings().WORLD_ID)
            for tick_id in range(start_tick + 1, end_tick + 1):
                unresolved = False

                if self._story_pacing_engine is not None:
                    row = await self._run_engine_safe(
                        "story_pacing", tick_id,
                        self._story_pacing_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["story_pacing"].append(row)

                if tick_id % self._gossip_interval == 0:
                    if self._distributed_lease_enabled:
                        try:
                            gossip_unresolved, gossip_row = await self._run_distributed_engine_tick(
                                session=session,
                                engine="gossip",
                                tick_id=tick_id,
                                runner=lambda: self._gossip_handler.run_tick(session=session, tick_id=tick_id),
                            )
                        except Exception as exc:
                            LOGGER.error(
                                "tick_engine_error",
                                extra={"engine": "gossip", "tick_id": tick_id, "error": str(exc)},
                            )
                            if self._engine_status_store is not None:
                                self._engine_status_store.record_error("gossip", tick_id, str(exc))
                            gossip_row = None
                            gossip_unresolved = False
                        else:
                            if gossip_row is not None and self._engine_status_store is not None:
                                self._engine_status_store.record_success("gossip", tick_id)
                        if gossip_row is not None:
                            response["gossip"].append(gossip_row)
                        unresolved = unresolved or gossip_unresolved
                    else:
                        gossip_done = await self._is_tick_done(session=session, key="gossip_ticks", tick_id=tick_id)
                        if not gossip_done:
                            gossip_row = await self._run_engine_safe(
                                "gossip", tick_id,
                                self._gossip_handler.run_tick(session=session, tick_id=tick_id),
                            )
                            await self._mark_tick_done(session=session, key="gossip_ticks", tick_id=tick_id)
                            if gossip_row is not None:
                                response["gossip"].append(gossip_row)

                if tick_id % self._event_interval == 0:
                    if self._distributed_lease_enabled:
                        try:
                            event_unresolved, event_row = await self._run_distributed_engine_tick(
                                session=session,
                                engine="event",
                                tick_id=tick_id,
                                runner=lambda: self._event_handler.run_tick(session=session, tick_id=tick_id),
                            )
                        except Exception as exc:
                            LOGGER.error(
                                "tick_engine_error",
                                extra={"engine": "event", "tick_id": tick_id, "error": str(exc)},
                            )
                            if self._engine_status_store is not None:
                                self._engine_status_store.record_error("event", tick_id, str(exc))
                            event_row = None
                            event_unresolved = False
                        else:
                            if event_row is not None and self._engine_status_store is not None:
                                self._engine_status_store.record_success("event", tick_id)
                        if event_row is not None:
                            response["event"].append(event_row)
                        unresolved = unresolved or event_unresolved
                    else:
                        event_done = await self._is_tick_done(session=session, key="event_ticks", tick_id=tick_id)
                        if not event_done:
                            event_row = await self._run_engine_safe(
                                "event", tick_id,
                                self._event_handler.run_tick(session=session, tick_id=tick_id),
                            )
                            await self._mark_tick_done(session=session, key="event_ticks", tick_id=tick_id)
                            if event_row is not None:
                                response["event"].append(event_row)

                if self._routine_engine is not None:
                    row = await self._run_engine_safe(
                        "routine", tick_id,
                        self._routine_engine.run_tick(
                            session=session, time_of_day=world_state.time_of_day, tick_id=tick_id,
                        ),
                    )
                    if row is not None:
                        response["routine"].append(row)

                if self._faction_politics_engine is not None:
                    row = await self._run_engine_safe(
                        "faction_politics", tick_id,
                        self._faction_politics_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["faction_politics"].append(row)

                if self._clique_formation_engine is not None:
                    row = await self._run_engine_safe(
                        "clique", tick_id,
                        self._clique_formation_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["clique"].append(row)

                if self._skill_progression_engine is not None:
                    row = await self._run_engine_safe(
                        "skill_progression", tick_id,
                        self._skill_progression_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["skill_progression"].append(row)

                if self._oath_engine is not None:
                    row = await self._run_engine_safe(
                        "oath", tick_id,
                        self._oath_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["oath"].append(row)

                if self._treaty_engine is not None:
                    row = await self._run_engine_safe(
                        "treaty", tick_id,
                        self._treaty_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["treaty"].append(row)

                if self._mood_contagion_engine is not None:
                    row = await self._run_engine_safe(
                        "mood_contagion", tick_id,
                        self._mood_contagion_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["mood_contagion"].append(row)

                if (
                    not skip_llm_engines
                    and self._chapter_engine is not None
                    and tick_id % self._chapter_interval == 0
                ):
                    row = await self._run_engine_safe(
                        "chapter", tick_id,
                        self._chapter_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["chapter"].append(row)

                if self._succession_engine is not None:
                    row = await self._run_engine_safe(
                        "succession", tick_id,
                        self._succession_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["succession"].append(row)

                if self._agenda_engine is not None:
                    row = await self._run_engine_safe(
                        "agenda", tick_id,
                        self._agenda_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["agenda"].append(row)

                if self._need_decay_engine is not None:
                    row = await self._run_engine_safe(
                        "need_decay", tick_id,
                        self._need_decay_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["need_decay"].append(row)

                if self._military_engine is not None:
                    row = await self._run_engine_safe(
                        "military", tick_id,
                        self._military_engine.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["military"].append(row)

                if self._event_quest_trigger is not None:
                    row = await self._run_engine_safe(
                        "event_quest", tick_id,
                        self._event_quest_trigger.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["event_quest"].append(row)

                if self._need_quest_trigger is not None:
                    row = await self._run_engine_safe(
                        "need_quest", tick_id,
                        self._need_quest_trigger.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["need_quest"].append(row)

                if self._world_state_quest_trigger is not None:
                    row = await self._run_engine_safe(
                        "world_state_quest", tick_id,
                        self._world_state_quest_trigger.run_tick(session=session, tick_id=tick_id),
                    )
                    if row is not None:
                        response["world_state_quest"].append(row)

                if unresolved:
                    break
                advanced_ticks += 1

            if tick_delta <= 0:
                advanced_seconds = 0
            else:
                advanced_seconds = int((time_delta_seconds * advanced_ticks) / tick_delta)
            state = await self._clock.advance(tick_delta=advanced_ticks, time_delta_seconds=advanced_seconds)
            response["clock"] = state.model_dump()

            self._advance_count += 1
            if (
                not skip_llm_engines
                and self._memory_consolidation_engine is not None
                and self._advance_count % self._consolidation_advance_interval == 0
            ):
                game_time = TimePoint(
                    year=world_state.year,
                    season=world_state.season,
                    day=world_state.day,
                    time_of_day=world_state.time_of_day,
                )
                consolidation_tick = start_tick + advanced_ticks
                consolidation_row = await self._run_engine_safe(
                    "memory_consolidation", consolidation_tick,
                    self._memory_consolidation_engine.run_tick(session, game_time=game_time),
                )
                response["consolidation"] = (
                    consolidation_row.get("consolidated", []) if consolidation_row is not None else []
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
    def engine_status(self) -> dict:
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
