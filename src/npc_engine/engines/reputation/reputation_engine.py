"""
Module: reputation_engine
Layer: engines
Purpose: 1-hop personal reputation propagation engine (EXP-52 slice-1).
         On each tick, for every source NPC S that is FRIENDLY+ toward the player,
         nudges trust on every bridge NPC B that has an existing edge toward the player,
         provided S's standing toward B meets the bridge threshold.
Does NOT: open Neo4j sessions, run Cypher, call LLMs, or create new RELATES_TO edges.
Dependencies injected: PropagationConfig, RelationReader, apply_nudge_fn callable.
Used by: tick scheduler (future slice — not wired in this slice).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from neo4j import AsyncSession

from npc_engine.engines.relationship.standing import Standing, derive_standing
from npc_engine.engines.reputation.propagation_config import PropagationConfig
from npc_engine.utils.errors import RelationEdgeNotFoundError
from npc_engine.utils.logging import get_logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Ordered Standing bands from most hostile to most allied (used for >= comparisons).
_STANDING_ORDER: list[Standing] = [
    Standing.HOSTILE,
    Standing.WARY,
    Standing.NEUTRAL,
    Standing.FRIENDLY,
    Standing.ALLIED,
]

logger: logging.Logger = get_logger()

# Type alias for the nudge callable injected by the caller.
NudgeFn = Callable[..., Awaitable[None]]


def _standing_gte(a: Standing, b: Standing) -> bool:
    """Return True if Standing a is greater than or equal to Standing b."""
    return _STANDING_ORDER.index(a) >= _STANDING_ORDER.index(b)


class ReputationEngine:
    """1-hop personal reputation propagation engine.

    On each tick, propagates the player's reputation through 1 hop of the NPC
    social graph by nudging trust on existing RELATES_TO edges.

    Attributes:
        _config: Tuning constants loaded from reputation_rules.yaml.
        _reader: RelationReader used to fetch edge scalars.
        _apply_nudge_fn: Async callable that writes the nudge to the graph layer.
    """

    def __init__(
        self,
        config: PropagationConfig,
        relation_reader: Any,
        apply_nudge_fn: NudgeFn,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            config: Validated PropagationConfig instance.
            relation_reader: RelationReader providing get_relation_scalars(src_id, dst_id).
            apply_nudge_fn: Async callable signature:
                apply_nudge_fn(session, *, src_id, dst_id, delta_trust, delta_affection).
                In production this is graph.reputation_nudge.apply_trust_nudge.
        """
        self._config = config
        self._reader = relation_reader
        self._apply_nudge_fn = apply_nudge_fn

    async def run_tick(
        self,
        session: AsyncSession,
        player_id: str,
        npc_ids: list[str],
    ) -> None:
        """Run one propagation tick for all candidate source NPCs.

        No-op when config.enabled is False.

        Args:
            session: Active Neo4j async session forwarded to the nudge writer.
            player_id: ID of the player character whose reputation propagates.
            npc_ids: List of NPC IDs to consider as sources and bridges.
        """
        if not self._config.enabled:
            return

        min_src = Standing(self._config.min_source_standing)
        min_bridge = Standing(self._config.min_bridge_standing)

        for source_id in npc_ids:
            await self._propagate_from_source(
                session=session,
                source_id=source_id,
                player_id=player_id,
                npc_ids=npc_ids,
                min_src=min_src,
                min_bridge=min_bridge,
            )

    async def _propagate_from_source(
        self,
        *,
        session: AsyncSession,
        source_id: str,
        player_id: str,
        npc_ids: list[str],
        min_src: Standing,
        min_bridge: Standing,
    ) -> None:
        """Propagate from one source NPC; skip silently if edge missing or standing too low."""
        try:
            scalars_s_player = await self._reader.get_relation_scalars(
                src_id=source_id, dst_id=player_id
            )
        except RelationEdgeNotFoundError:
            return

        src_standing = derive_standing(**scalars_s_player)
        if not _standing_gte(src_standing, min_src):
            return

        source_trust = scalars_s_player["trust"]

        for bridge_id in npc_ids:
            if bridge_id == source_id or bridge_id == player_id:
                continue
            await self._maybe_nudge_bridge(
                session=session,
                source_id=source_id,
                bridge_id=bridge_id,
                player_id=player_id,
                source_trust=source_trust,
                min_bridge=min_bridge,
            )

    async def _maybe_nudge_bridge(
        self,
        *,
        session: AsyncSession,
        source_id: str,
        bridge_id: str,
        player_id: str,
        source_trust: int,
        min_bridge: Standing,
    ) -> None:
        """Nudge bridge NPC trust toward player if source→bridge and bridge→player edges pass thresholds."""
        try:
            scalars_s_bridge = await self._reader.get_relation_scalars(
                src_id=source_id, dst_id=bridge_id
            )
        except RelationEdgeNotFoundError:
            return

        bridge_standing = derive_standing(**scalars_s_bridge)
        if not _standing_gte(bridge_standing, min_bridge):
            return

        try:
            await self._reader.get_relation_scalars(src_id=bridge_id, dst_id=player_id)
        except RelationEdgeNotFoundError:
            return  # first-slice: skip B if no existing edge to player

        await self._compute_and_apply_nudge(
            session=session,
            source_id=source_id,
            bridge_id=bridge_id,
            player_id=player_id,
            source_trust=source_trust,
        )

    async def _compute_and_apply_nudge(
        self,
        *,
        session: AsyncSession,
        source_id: str,
        bridge_id: str,
        player_id: str,
        source_trust: int,
    ) -> None:
        """Compute nudge magnitude, log it, and write it via the injected nudge function."""
        nudge = max(0, min(self._config.max_nudge_per_tick, source_trust // 10))
        logger.info(
            "reputation_nudge",
            extra={
                "src_npc": source_id,
                "bridge": bridge_id,
                "player_id": player_id,
                "delta_trust": nudge,
            },
        )
        await self._apply_nudge_fn(
            session,
            src_id=bridge_id,
            dst_id=player_id,
            delta_trust=nudge,
            delta_affection=0,
        )
