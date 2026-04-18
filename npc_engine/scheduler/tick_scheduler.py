"""
tick_scheduler.py - Coordinates game clock and tick execution for engines.

Does NOT: define gossip/event engine internals.

Dependencies injected: GameClock, GossipHandler, EventHandler.
"""

from neo4j import AsyncSession
import asyncio
from collections.abc import Awaitable, Callable

from scheduler.game_clock import GameClock
from scheduler.tick_lease import TickLeaseRepository, TickLeaseRepositoryProtocol


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
    """Orchestrates conditional gossip and event ticks."""

    def __init__(
        self,
        clock: GameClock,
        gossip_handler,
        event_handler,
        gossip_interval: int,
        event_interval: int,
        *,
        distributed_lease_enabled: bool = False,
        scheduler_id: str = "main",
        lease_owner_id: str = "worker",
        lease_ttl_seconds: int = 30,
        lease_repo: TickLeaseRepositoryProtocol | None = None,
    ):
        self._clock = clock
        self._gossip_handler = gossip_handler
        self._event_handler = event_handler
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
        """Advance clock and run due handlers at resulting tick."""

        async with self._lock:
            start_tick = self._clock.state.tick_id
            end_tick = start_tick + max(0, tick_delta)
            advanced_ticks = 0
            response: dict = {
                "clock": self._clock.state.model_dump(),
                "gossip": [],
                "event": [],
            }
            for tick_id in range(start_tick + 1, end_tick + 1):
                unresolved = False
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
                if unresolved:
                    break
                advanced_ticks += 1
            if tick_delta <= 0:
                advanced_seconds = 0
            else:
                advanced_seconds = int((time_delta_seconds * advanced_ticks) / tick_delta)
            state = await self._clock.advance(tick_delta=advanced_ticks, time_delta_seconds=advanced_seconds)
            response["clock"] = state.model_dump()
            return response

    @property
    def state(self):
        return self._clock.state

    @property
    def next_gossip_tick(self) -> int:
        tick = self._clock.state.tick_id
        return tick + (self._gossip_interval - (tick % self._gossip_interval))

    @property
    def next_event_tick(self) -> int:
        tick = self._clock.state.tick_id
        return tick + (self._event_interval - (tick % self._event_interval))
