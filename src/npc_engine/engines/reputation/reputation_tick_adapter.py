"""
Module: reputation_tick_adapter
Layer: engines
Purpose: Tick-scheduler adapter wrapping ReputationEngine with the
         run_tick(session, tick_id) -> dict signature expected by TickScheduler.
         Fetches active NPC IDs from graph.character_reader each tick and
         delegates propagation to the underlying ReputationEngine.
         Returns {"nudges": 0} immediately when config.enabled is False
         (zero runtime cost, engine never touches the graph).
         Accepts a relation_reader_factory callable to construct a session-scoped
         RelationReader per tick (RelationReader holds a session reference and
         must not be shared across ticks).
Does NOT: run Cypher queries directly (delegated to graph.character_reader).
Dependencies: engines.reputation.reputation_engine.ReputationEngine,
              engines.reputation.propagation_config.PropagationConfig,
              graph.character_reader (protocol-injected reader)
Dependencies injected: ReputationEngine, character_reader, player_id, PropagationConfig,
                       relation_reader_factory via __init__.
Used by: scheduler.tick_scheduler (wired via dependencies_engines.py).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol

from neo4j import AsyncSession

from npc_engine.engines.reputation.propagation_config import PropagationConfig
from npc_engine.engines.reputation.reputation_engine import ReputationEngine
from npc_engine.utils.logging import get_logger

logger: logging.Logger = get_logger()


class _CharacterReaderProtocol(Protocol):
    """Structural protocol for any object that can return NPC IDs from the graph."""

    async def get_npc_ids(self, session: AsyncSession) -> list[str]:
        """Return IDs of all active non-player characters."""


class ReputationTickAdapter:
    """Tick-scheduler adapter for ReputationEngine.

    Bridges the mismatch between TickScheduler's expected
    ``run_tick(session, tick_id) -> dict`` signature and
    ReputationEngine's ``run_tick(session, player_id, npc_ids) -> None``.

    Because RelationReader holds a session reference set at construction time,
    a new RelationReader instance must be created for each tick. The adapter
    accepts a ``relation_reader_factory`` callable — ``factory(session)`` —
    and injects the fresh reader into the engine before each delegation.

    On each tick:
    1. Returns {"nudges": 0} immediately when config.enabled is False.
    2. Builds a fresh RelationReader via relation_reader_factory(session).
    3. Fetches all active NPC IDs via character_reader.get_npc_ids(session).
    4. Delegates to engine.run_tick(session, player_id=..., npc_ids=...).
    5. Returns {"nudges": len(npc_ids)} as a coarse activity counter.

    Attributes:
        _engine: The wrapped ReputationEngine instance.
        _character_reader: Graph-layer reader for NPC ID enumeration.
        _player_id: Player ID whose reputation propagates each tick.
        _config: PropagationConfig; checked for enabled flag before any I/O.
        _relation_reader_factory: Callable[session] -> RelationReader.
    """

    def __init__(
        self,
        engine: ReputationEngine,
        character_reader: _CharacterReaderProtocol,
        player_id: str,
        config: PropagationConfig,
        relation_reader_factory: Callable[[AsyncSession], Any] | None = None,
    ) -> None:
        """Initialise the adapter with injected dependencies.

        Args:
            engine: Configured ReputationEngine instance.
            character_reader: Graph reader implementing get_npc_ids(session).
            player_id: ID of the player character for reputation propagation.
            config: PropagationConfig; used for the enabled guard.
            relation_reader_factory: Optional callable ``(session) -> RelationReader``.
                When provided, a fresh RelationReader is built per tick and
                injected into the engine before delegation.
        """
        self._engine = engine
        self._character_reader = character_reader
        self._player_id = player_id
        self._config = config
        self._relation_reader_factory = relation_reader_factory

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int,
    ) -> dict[str, Any]:
        """Run one reputation propagation tick.

        Returns {"nudges": 0} immediately when engine is disabled to avoid
        any graph I/O. Otherwise builds a session-scoped RelationReader,
        fetches NPC IDs, and delegates to the engine.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick (logged for observability).

        Returns:
            Dict with key ``nudges``: count of NPC IDs processed (0 when disabled).
        """
        if not self._config.enabled:
            return {"nudges": 0}

        if self._relation_reader_factory is not None:
            self._engine._reader = self._relation_reader_factory(session)  # noqa: SLF001

        npc_ids = await self._character_reader.get_npc_ids(session)
        await self._engine.run_tick(
            session,
            player_id=self._player_id,
            npc_ids=npc_ids,
        )
        logger.info(
            "reputation_tick_done",
            extra={"tick_id": tick_id, "npc_count": len(npc_ids)},
        )
        return {"nudges": len(npc_ids)}
