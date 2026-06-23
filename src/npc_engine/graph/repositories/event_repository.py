"""
Module: event_repository
Layer: graph
Purpose: Neo4j adapter for the event graph domain. Opens a session per call from the
         injected GraphDB and delegates to event_queries / event_emission_service /
         witnessed_service / causality_service, so EventHandler depends on the
         EventGraphPort abstraction and holds no session. The atomic emit runs its
         run_in_tx unit-of-work inside event_emission_service (DEC-122 / SEV-24).
Does NOT: select templates, match disruption rules, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_event_handler).
"""

from __future__ import annotations

from npc_engine.graph.causality_service import record_causation
from npc_engine.graph.db import GraphDB
from npc_engine.graph.event.event_emission_service import RoutineOverridePlan, emit_event_atomic
from npc_engine.graph.event.event_queries import get_characters_at_location, get_locations_by_tag
from npc_engine.graph.event.event_writer import _EventNode
from npc_engine.graph.witnessed_service import record_witness


class Neo4jEventRepository:
    """Session-per-call Neo4j adapter for the event domain (EventGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_locations_by_tag(self, *, location_tag: str) -> list[str]:
        """Open a session and return location ids carrying the given tag."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_locations_by_tag(session, location_tag)

    async def emit_event_atomic(
        self,
        *,
        event: _EventNode,
        event_id: str,
        location_id: str,
        tick_id: int,
        faction_id: str | None,
        reputation_delta: int | None,
        routine_overrides: list[RoutineOverridePlan],
        world_condition_event_type: str | None,
        world_id: str,
    ) -> None:
        """Open a session and persist the event + side effects atomically."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await emit_event_atomic(
                session,
                event=event,
                event_id=event_id,
                location_id=location_id,
                tick_id=tick_id,
                faction_id=faction_id,
                reputation_delta=reputation_delta,
                routine_overrides=routine_overrides,
                world_condition_event_type=world_condition_event_type,
                world_id=world_id,
            )

    async def get_characters_at_location(self, *, location_id: str) -> list[str]:
        """Open a session and return ids of active characters at the location."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_characters_at_location(session, location_id)

    async def record_witnesses(
        self,
        *,
        witness_ids: list[str],
        subject_id: str,
        event_id: str,
        action_type: str,
        tick: int,
        clarity: int,
        interpretation: str,
    ) -> None:
        """Open one session and record a WITNESSED edge for each witness."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            for witness_id in witness_ids:
                await record_witness(
                    session,
                    witness_id=witness_id,
                    subject_id=subject_id,
                    event_id=event_id,
                    action_type=action_type,
                    tick=tick,
                    clarity=clarity,
                    interpretation=interpretation,
                )

    async def record_causation(
        self,
        *,
        effect_node_id: str,
        effect_node_type: str,
        cause_event_id: str,
        causation_strength: int,
        cause_type: str,
        tick_lag: int,
    ) -> None:
        """Open a session and record a CAUSED_BY edge from effect to cause."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await record_causation(
                session,
                effect_node_id=effect_node_id,
                effect_node_type=effect_node_type,
                cause_event_id=cause_event_id,
                causation_strength=causation_strength,
                cause_type=cause_type,
                tick_lag=tick_lag,
            )
