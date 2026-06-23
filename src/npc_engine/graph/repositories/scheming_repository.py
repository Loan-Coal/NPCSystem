"""
Module: scheming_repository
Layer: graph
Purpose: Neo4j adapter for the scheming graph domain. Opens a session per call from the
         injected GraphDB and delegates to scheme_reader (reads), scheme_writer (writes),
         graph_reader (NPC location), and event_writer (atomic step emit via run_in_tx),
         so SchemingEngine, SchemeAdvanceTick, and SchemeDetectionTick depend on
         SchemingGraphPort and hold no Neo4j session (DEC-122 / SEV-24).
Does NOT: apply scheme logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_scheme_advance_tick,
         get_scheme_detection_tick).
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncTransaction

from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.event.event_writer import upsert_event
from npc_engine.graph.graph_reader import get_npc_location_id
from npc_engine.graph.intrigue.scheme_reader import (
    ActiveSchemeProgress,
    SchemeRecord,
    get_active_schemes,
    get_all_active_schemes_with_steps,
)
from npc_engine.graph.intrigue.scheme_reader import get_discoverable_scheme_ids
from npc_engine.graph.intrigue.scheme_writer import add_scheme_step, mark_scheme_discovered, upsert_scheme
from npc_engine.graph.infra.transaction_coordinator import run_in_tx


class Neo4jSchemingRepository:
    """Session-per-call Neo4j adapter for the scheming domain (SchemingGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_active_schemes(self, npc_id: str) -> list[SchemeRecord]:
        """Open a session and return all active schemes for the NPC."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_active_schemes(session, npc_id)

    async def upsert_scheme(
        self,
        *,
        scheme_id: str,
        npc_id: str,
        goal: str,
        tick: int,
    ) -> None:
        """Open a session and upsert a Scheme node + EXECUTES_SCHEME edge."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await upsert_scheme(
                session=session,
                scheme_id=scheme_id,
                npc_id=npc_id,
                goal=goal,
                tick=tick,
            )

    async def add_scheme_step(
        self,
        *,
        scheme_id: str,
        event_id: str,
        step_order: int,
        completed: bool,
    ) -> None:
        """Open a session and create/update a single SCHEME_STEP edge."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await add_scheme_step(
                session=session,
                scheme_id=scheme_id,
                event_id=event_id,
                step_order=step_order,
                completed=completed,
            )

    async def get_all_active_schemes_with_steps(self) -> list[ActiveSchemeProgress]:
        """Open a session and return all active schemes with step counts."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_all_active_schemes_with_steps(session)

    async def get_npc_location_id(self, npc_id: str) -> str | None:
        """Open a session and return the NPC's current location id, or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_npc_location_id(session, npc_id)

    async def emit_scheme_step_atomic(
        self,
        *,
        event: Any,
        scheme_id: str,
        event_id: str,
        step_order: int,
        completed: bool,
    ) -> None:
        """Atomically upsert the covert Event and link it as the next SCHEME_STEP.

        Both writes share one transaction so a failure between them cannot leave an
        orphan Event with no SCHEME_STEP link (SEV-01 / L2-07).

        Args:
            event: Registry-validated event model to upsert.
            scheme_id: Scheme node ID to attach the step to.
            event_id: Event node ID for the SCHEME_STEP edge.
            step_order: Ordinal position of the new step.
            completed: Whether the step is already completed.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:

            async def _emit(tx: AsyncTransaction) -> None:
                await upsert_event(tx=tx, event=event)
                await add_scheme_step(
                    tx=tx,
                    scheme_id=scheme_id,
                    event_id=event_id,
                    step_order=step_order,
                    completed=completed,
                )

            await run_in_tx(session, _emit)

    async def get_discoverable_scheme_ids(self, min_steps: int) -> list[str]:
        """Return active scheme IDs that are witnessed and have enough steps.

        Args:
            min_steps: Minimum SCHEME_STEP count before a scheme is discoverable.

        Returns:
            List of discoverable scheme IDs (may be empty).
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_discoverable_scheme_ids(session, min_steps)

    async def mark_scheme_discovered(self, scheme_id: str) -> bool:
        """Flip an active scheme's status to 'discovered' (idempotent).

        Args:
            scheme_id: Scheme node ID to mark discovered.

        Returns:
            True if the scheme transitioned active→discovered, else False.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await mark_scheme_discovered(session, scheme_id)
