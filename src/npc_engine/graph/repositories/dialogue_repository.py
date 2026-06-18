"""
Module: dialogue_repository
Layer: graph
Purpose: Neo4j adapter for DialogueGraphPort — opens a session per operation.
Does NOT: import from engines layer; hold long-lived sessions.
Dependencies: graph.db, graph.graph_reader, graph.world_state_reader, graph.graph_writer,
              graph.routine_queries, engines.dialogue.dialogue_models, world.world_state,
              utils.errors
Used by: api.dependencies_stores (composition root)
Dependencies injected: GraphDB
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from npc_engine.config import Settings
from npc_engine.graph.db import GraphDB
from npc_engine.graph.graph_reader import get_npc_archetype, get_npc_voice_descriptor
from npc_engine.graph.graph_writer import apply_relation_delta, ensure_relation_edge
from npc_engine.graph.routine_queries import set_routine_override as _set_routine_override
from npc_engine.graph.world_state_reader import get_world_state as _get_world_state
from npc_engine.utils.errors import RelationEdgeNotFoundError

if TYPE_CHECKING:
    from npc_engine.world.world_state import WorldState

_logger = logging.getLogger(__name__)


class Neo4jDialogueRepository:
    """Graph-layer adapter for dialogue graph operations.

    Opens one Neo4j session per operation — the engine never holds a session.
    Structurally conforms to DialogueGraphPort (no import of the protocol keeps
    the graph layer free from engines imports).
    Dependencies injected: graph_db.
    """

    def __init__(self, graph_db: GraphDB) -> None:
        """Initialise with an injected GraphDB instance.

        Args:
            graph_db: Shared database connection pool.
        """
        self._graph_db = graph_db

    async def get_npc_archetype(self, npc_id: str) -> str | None:
        """Fetch the archetype string for an NPC node.

        Args:
            npc_id: NPC identifier.
        Returns:
            Archetype string, or None if not set.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_npc_archetype(session, npc_id)

    async def get_npc_voice_descriptor(self, npc_id: str) -> str | None:
        """Fetch the voice_descriptor property for an NPC node.

        Args:
            npc_id: NPC identifier.
        Returns:
            Voice descriptor string, or None if not set.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_npc_voice_descriptor(session, npc_id)

    async def get_world_state(self, world_id: str) -> WorldState | None:
        """Return the current WorldState for the given world node.

        Args:
            world_id: World node identifier.
        Returns:
            WorldState model, or None if the node is absent.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await _get_world_state(session=session, world_id=world_id)

    async def apply_relation_deltas(
        self,
        *,
        npc_id: str,
        player_id: str,
        relation_deltas: Any,
        cause_id: str,
        tick_id: int,
        settings: Settings,
    ) -> None:
        """Apply relation deltas to the RELATES_TO edge; create it on first contact.

        On RelationEdgeNotFoundError a baseline edge is created then the delta
        is retried in a second session-per-call. This moves the first-contact
        retry logic out of relation_mutator into the graph layer.

        Args:
            npc_id: Source NPC identifier.
            player_id: Destination player identifier.
            relation_deltas: Pydantic model with .model_dump() — typed Any to avoid engines import.
            cause_id: Opaque cause string for audit logging.
            tick_id: Game tick for the log entry.
            settings: Application settings forwarded to the graph writer.
        """
        first_contact = False
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            try:
                await apply_relation_delta(
                    session=session,
                    settings=settings,
                    src_id=npc_id,
                    dst_id=player_id,
                    deltas=relation_deltas.model_dump(),
                    cause_id=cause_id,
                    tick_id=tick_id,
                )
            except RelationEdgeNotFoundError:
                first_contact = True
                _logger.info(
                    "relation_first_contact",
                    extra={"npc_id": npc_id, "player_id": player_id, "tick_id": tick_id},
                )
        if first_contact:
            await self._apply_first_contact_retry(
                npc_id=npc_id,
                player_id=player_id,
                relation_deltas=relation_deltas,
                cause_id=cause_id,
                tick_id=tick_id,
                settings=settings,
            )

    async def _apply_first_contact_retry(
        self,
        *,
        npc_id: str,
        player_id: str,
        relation_deltas: Any,
        cause_id: str,
        tick_id: int,
        settings: Settings,
    ) -> None:
        """Ensure edge exists then re-apply delta — called only on first-contact."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await ensure_relation_edge(session=session, src_id=npc_id, dst_id=player_id)
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await apply_relation_delta(
                session=session,
                settings=settings,
                src_id=npc_id,
                dst_id=player_id,
                deltas=relation_deltas.model_dump(),
                cause_id=cause_id,
                tick_id=tick_id,
            )

    async def set_routine_override(
        self,
        *,
        character_id: str,
        location_id: str,
        expires_at_tick: int,
    ) -> None:
        """Override a character's routine destination until the expiry tick.

        Args:
            character_id: Character node identifier.
            location_id: Location identifier to override with.
            expires_at_tick: Tick at which the override expires.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await _set_routine_override(
                session=session,
                character_id=character_id,
                location_id=location_id,
                expires_at_tick=expires_at_tick,
            )
