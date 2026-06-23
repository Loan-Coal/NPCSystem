"""
Module: gossip_repository
Layer: graph
Purpose: Neo4j adapter for the gossip graph domain. Opens a session per call from the
         injected GraphDB and delegates to gossip_queries (pair selection), gossip_batch_queries
         (batch event/trust reads and knowledge writes), gossip_write_queries (secret and
         relation-log writes), rumor_service (rumor creation and belief), and goal_queries
         (pair weighting). The log_gossip method encapsulates the optimistic-concurrency
         retry (CAS) that previously lived in engines/gossip/edge_updater.py.
Does NOT: apply distortion logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_gossip_handler).
"""

from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

from npc_engine.common.json_utils import dump_json, parse_json_list
from npc_engine.graph.db import GraphDB
from npc_engine.graph.needs_goals.goal_queries import get_goals_for_character
from npc_engine.graph.gossip.gossip_batch_queries import (
    select_batch_event_trust,
    select_gossip_secret,
    write_batch_knowledge_propagation,
)
from npc_engine.graph.gossip.gossip_queries import fetch_gossip_pairs, fetch_known_node_ids
from npc_engine.graph.gossip.gossip_write_queries import (
    fetch_relation_log,
    update_relation_log,
    write_secret_propagation,
)
from npc_engine.graph.gossip.rumor_service import believe_rumor, create_rumor

_LOG_GOSSIP_MAX_RETRIES = 3
_LOG_GOSSIP_TAIL = 20
_LOG_GOSSIP_CAUSE = "gossip"


class Neo4jGossipRepository:
    """Session-per-call Neo4j adapter for the gossip domain (GossipGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def fetch_gossip_pairs(self) -> list[dict[str, Any]]:
        """Return all co-located active NPC pairs eligible for gossip exchange."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await fetch_gossip_pairs(session)

    async def get_goals_for_character(
        self, character_id: str, *, k: int, status_filter: str
    ) -> list[dict[str, Any]]:
        """Return up to k goals for the character filtered by status."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_goals_for_character(
                session, character_id=character_id, k=k, status_filter=status_filter
            )

    async def fetch_known_node_ids(self, character_id: str) -> set[str]:
        """Return node IDs the character knows about via KNOWS_ABOUT."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await fetch_known_node_ids(session, character_id=character_id)

    async def select_batch_event_trust(
        self, pairs: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        """Fetch event and trust data for all sharer/receiver pairs in one query."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await select_batch_event_trust(session, pairs=pairs)

    async def write_batch_knowledge_propagation(self, writes: list[dict[str, Any]]) -> None:
        """Merge KNOWS_ABOUT edges for all receiver/event pairs in one query."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await write_batch_knowledge_propagation(session, writes=writes)

    async def create_rumor(
        self,
        *,
        content: str,
        origin_event_id: str | None,
        created_at_tick: int,
        severity: int,
        is_fabricated: bool,
    ) -> str:
        """Merge a root Rumor node and return its ID."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await create_rumor(
                session,
                content=content,
                origin_event_id=origin_event_id,
                created_at_tick=created_at_tick,
                severity=severity,
                is_fabricated=is_fabricated,
            )

    async def believe_rumor(
        self,
        *,
        character_id: str,
        rumor_id: str,
        confidence: int,
        tick: int,
        from_character_id: str | None,
    ) -> None:
        """Create or update a BELIEVES_RUMOR edge from character to rumor."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await believe_rumor(
                session,
                character_id=character_id,
                rumor_id=rumor_id,
                confidence=confidence,
                tick=tick,
                from_character_id=from_character_id,
            )

    async def select_gossip_secret(self, sharer_id: str) -> dict[str, Any] | None:
        """Return the most severe secret the sharer holds, or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await select_gossip_secret(session, sharer_id=sharer_id)

    async def log_gossip(
        self, *, src_id: str, dst_id: str, tick_id: int, trust_delta: int
    ) -> None:
        """Append a gossip entry to the RELATES_TO delta log with optimistic CAS retry.

        Up to _LOG_GOSSIP_MAX_RETRIES compare-and-swap attempts are made before
        giving up silently. Missing RELATES_TO edges are silently skipped.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            for _ in range(_LOG_GOSSIP_MAX_RETRIES):
                current_log = await fetch_relation_log(session, src_id=src_id, dst_id=dst_id)
                if current_log is None:
                    return
                updated = _append_log(
                    raw_log=current_log,
                    tick_id=tick_id,
                    cause=_LOG_GOSSIP_CAUSE,
                    trust_delta=trust_delta,
                )
                wrote = await update_relation_log(
                    session,
                    src_id=src_id,
                    dst_id=dst_id,
                    expected_delta_log=current_log,
                    delta_log=updated,
                    trust_delta=trust_delta,
                )
                if wrote:
                    return

    async def propagate_secret(
        self,
        *,
        receiver_id: str,
        secret_id: str,
        source_character_id: str,
        tick_id: int,
        distorted: bool,
    ) -> None:
        """Merge a KNOWS_SECRET edge from the receiver to the secret."""
        from npc_engine.common.knowledge_types import (
            KNOWLEDGE_STATE_KNOWS,
            KNOWLEDGE_STATE_RUMOR,
        )

        knowledge_state = KNOWLEDGE_STATE_RUMOR if distorted else KNOWLEDGE_STATE_KNOWS
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await write_secret_propagation(
                session,
                receiver_id=receiver_id,
                secret_id=secret_id,
                source_character_id=source_character_id,
                tick_id=tick_id,
                knowledge_state=knowledge_state,
            )


def _append_log(raw_log: str, tick_id: int, cause: str, trust_delta: int) -> str:
    """Append one gossip delta entry and trim to the last _LOG_GOSSIP_TAIL entries."""
    payload = parse_json_list(raw_log)
    payload.append(
        {
            "tick_id": tick_id,
            "cause_id": cause,
            "deltas": {"trust": trust_delta, "fear": 0, "affection": 0},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    return dump_json(payload[-_LOG_GOSSIP_TAIL:])
