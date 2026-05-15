"""
tick_scheduler.py - Coordinates game clock and tick execution for engines.

Does NOT: define gossip/event/routine engine internals.

Dependencies injected: GameClock, GossipHandler, EventHandler, RoutineEngine,
                       MemoryConsolidationEngine (optional).
"""

from neo4j import AsyncSession
import asyncio
from collections.abc import Awaitable, Callable

from npc_engine.engines.base_engine import BaseEngine
from npc_engine.scheduler.game_clock import ClockState, GameClock
from npc_engine.scheduler.tick_lease import TickLeaseRepository, TickLeaseRepositoryProtocol
from npc_engine.world.time_utils import TimePoint
from npc_engine.world.world_reader import get_world_state


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
        consolidation_advance_interval: int = 1,
        distributed_lease_enabled: bool = False,
        scheduler_id: str = "main",
        lease_owner_id: str = "worker",
        lease_ttl_seconds: int = 30,
        lease_repo: TickLeaseRepositoryProtocol | None = None,
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
            consolidation_advance_interval: Run consolidation every N advances; clamped to 1.
            distributed_lease_enabled: When True, use ``lease_repo`` for cross-worker
                tick deduplication instead of the local SchedulerState Cypher queries.
            scheduler_id: Unique identifier for the scheduler node in Neo4j.
            lease_owner_id: Worker identifier passed to the lease repository.
            lease_ttl_seconds: Lease TTL passed to the lease repository; clamped to 1.
            lease_repo: Optional pre-built lease repository; constructed from
                ``scheduler_id``, ``lease_owner_id``, and ``lease_ttl_seconds`` when None.
        """

        self._clock = clock
        self._gossip_handler = gossip_handler
        self._event_handler = event_handler
        self._routine_engine = routine_engine
        self._faction_politics_engine = faction_politics_engine
        self._story_pacing_engine = story_pacing_engine
        self._memory_consolidation_engine = memory_consolidation_engine
        self._consolidation_advance_interval = max(1, consolidation_advance_interval)
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

    async def advance(self, session: AsyncSession, tick_delta: int, time_delta_seconds: int) -> dict:
        """Advance the clock and run any handlers that are due at the resulting tick.

        Iterates each tick in ``[current+1, current+tick_delta]``. A tick is skipped
        for the relevant engine if it was already handled (via local state or distributed
        lease). When distributed leases are enabled and a tick is unresolved (claimed by
        another worker but not yet done), iteration stops early.

        Args:
            session: Active Neo4j async session.
            tick_delta: Number of ticks to advance; non-positive values are no-ops for
                the clock but the method still returns the current state.
            time_delta_seconds: In-game seconds proportionally advanced alongside ticks.

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
            }
            world_state = await get_world_state(session=session)
            for tick_id in range(start_tick + 1, end_tick + 1):
                unresolved = False

                if self._story_pacing_engine is not None:
                    pacing_row = await self._story_pacing_engine.run_tick(
                        session=session, tick_id=tick_id
                    )
                    response["story_pacing"].append(pacing_row)

                if tick_id % self._gossip_interval == 0:
                    if self._distributed_lease_enabled:
                        gossip_unresolved, gossip_row = await self._run_distributed_engine_tick(
                            session=session,
                            engine="gossip",
                            tick_id=tick_id,
                            runner=lambda: self._gossip_handler.run_tick(session=session, tick_id=tick_id),
                        )
                        if gossip_row is not None:
                            response["gossip"].append(gossip_row)
                        unresolved = unresolved or gossip_unresolved
                    else:
                        gossip_done = await self._is_tick_done(session=session, key="gossip_ticks", tick_id=tick_id)
                        if not gossip_done:
                            gossip_row = await self._gossip_handler.run_tick(session=session, tick_id=tick_id)
                            await self._mark_tick_done(session=session, key="gossip_ticks", tick_id=tick_id)
                            response["gossip"].append(gossip_row)
                if tick_id % self._event_interval == 0:
                    if self._distributed_lease_enabled:
                        event_unresolved, event_row = await self._run_distributed_engine_tick(
                            session=session,
                            engine="event",
                            tick_id=tick_id,
                            runner=lambda: self._event_handler.run_tick(session=session, tick_id=tick_id),
                        )
                        if event_row is not None:
                            response["event"].append(event_row)
                        unresolved = unresolved or event_unresolved
                    else:
                        event_done = await self._is_tick_done(session=session, key="event_ticks", tick_id=tick_id)
                        if not event_done:
                            event_row = await self._event_handler.run_tick(session=session, tick_id=tick_id)
                            await self._mark_tick_done(session=session, key="event_ticks", tick_id=tick_id)
                            response["event"].append(event_row)
                if self._routine_engine is not None:
                    routine_row = await self._routine_engine.run_tick(
                        session=session,
                        time_of_day=world_state.time_of_day,
                        tick_id=tick_id,
                    )
                    response["routine"].append(routine_row)

                if self._faction_politics_engine is not None:
                    fp_row = await self._faction_politics_engine.run_tick(session=session)
                    response["faction_politics"].append(fp_row)

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
                self._memory_consolidation_engine is not None
                and self._advance_count % self._consolidation_advance_interval == 0
            ):
                game_time = TimePoint(
                    year=world_state.year,
                    season=world_state.season,
                    day=world_state.day,
                    time_of_day=world_state.time_of_day,
                )
                consolidation_row = await self._memory_consolidation_engine.run_tick(
                    session, game_time=game_time
                )
                response["consolidation"] = consolidation_row.get("consolidated", [])

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
