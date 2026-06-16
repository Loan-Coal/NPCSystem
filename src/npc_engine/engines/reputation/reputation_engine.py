"""
Module: reputation_engine
Layer: engines
Purpose: 1-hop personal reputation propagation engine (EXP-52 slice-1).
         On each tick, for every source NPC S that is FRIENDLY+ toward the player,
         nudges trust on every bridge NPC B that has an existing edge toward the player,
         provided S's standing toward B meets the bridge threshold.
Does NOT: open Neo4j sessions, run Cypher, call LLMs, or create new RELATES_TO edges.
          Reads/writes are delegated to the injected RelationReadPort + ReputationGraphPort.
Dependencies injected: PropagationConfig, RelationReadPort (reads), ReputationGraphPort (nudge write).
Used by: engines.reputation.reputation_tick_adapter (wired via dependencies_engines.py).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from npc_engine.engines.relationship.standing import Standing, derive_standing
from npc_engine.engines.reputation.propagation_config import PropagationConfig
from npc_engine.utils.errors import RelationEdgeNotFoundError
from npc_engine.utils.logging import get_logger

if TYPE_CHECKING:
    from npc_engine.engines.ports.relation_read_port import RelationReadPort
    from npc_engine.engines.ports.reputation_port import ReputationGraphPort

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


def _standing_gte(a: Standing, b: Standing) -> bool:
    """Return True if Standing a is greater than or equal to Standing b."""
    return _STANDING_ORDER.index(a) >= _STANDING_ORDER.index(b)


class ReputationEngine:
    """1-hop personal reputation propagation engine.

    On each tick, propagates the player's reputation through 1 hop of the NPC
    social graph by nudging trust on existing RELATES_TO edges.

    Attributes:
        _config: Tuning constants loaded from reputation_rules.yaml.
        _reader: RelationReadPort used to fetch edge scalars (session-per-call adapter).
        _repo: ReputationGraphPort that writes the bounded nudge to the graph layer.
    """

    def __init__(
        self,
        config: PropagationConfig,
        relation_reader: RelationReadPort,
        reputation_repo: ReputationGraphPort,
    ) -> None:
        """Initialise with injected dependencies (no Neo4j session — DEC-122 / SEV-24).

        Args:
            config: Validated PropagationConfig instance.
            relation_reader: RelationReadPort providing get_relation_scalars(src_id, dst_id).
            reputation_repo: ReputationGraphPort whose apply_trust_nudge writes the nudge.
        """
        self._config = config
        self._reader = relation_reader
        self._repo = reputation_repo

    async def run_tick(
        self,
        player_id: str,
        npc_ids: list[str],
        **_: object,
    ) -> None:
        """Run one propagation tick for all candidate source NPCs.

        No-op when config.enabled is False. The trailing ``**_`` swallows the
        scheduler's legacy ``session=`` kwarg during the SEV-24 migration.

        Args:
            player_id: ID of the player character whose reputation propagates.
            npc_ids: List of NPC IDs to consider as sources and bridges.
        """
        if not self._config.enabled:
            return

        min_src = Standing(self._config.min_source_standing)
        min_bridge = Standing(self._config.min_bridge_standing)

        for source_id in npc_ids:
            await self._propagate_from_source(
                source_id=source_id,
                player_id=player_id,
                npc_ids=npc_ids,
                min_src=min_src,
                min_bridge=min_bridge,
            )

    async def _propagate_from_source(
        self,
        *,
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
                source_id=source_id,
                bridge_id=bridge_id,
                player_id=player_id,
                source_trust=source_trust,
                min_bridge=min_bridge,
            )

    async def _maybe_nudge_bridge(
        self,
        *,
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
            source_id=source_id,
            bridge_id=bridge_id,
            player_id=player_id,
            source_trust=source_trust,
        )

    async def _compute_and_apply_nudge(
        self,
        *,
        source_id: str,
        bridge_id: str,
        player_id: str,
        source_trust: int,
    ) -> None:
        """Compute nudge magnitude, log it, and write it via the injected port."""
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
        await self._repo.apply_trust_nudge(
            src_id=bridge_id,
            dst_id=player_id,
            delta_trust=nudge,
            delta_affection=0,
        )
