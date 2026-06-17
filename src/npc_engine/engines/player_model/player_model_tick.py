"""
Module: player_model_tick
Layer: engines
Purpose: Tick-scheduler adapter that updates each NPC's model of the player (F1.4).
         For every co-located (npc, player) pair it reads the RELATES_TO scalars,
         derives a PlayerModelUpdate via the pure PlayerModelEngine, and persists it
         through the injected PlayerModelGraphPort.
Does NOT: run Cypher directly (delegates to injected read/write ports), call LLMs,
          hold a Neo4j session, or derive trust/intent itself.
Dependencies injected: PlayerModelEngine, PlayerLocationReadPort, RelationReadPort,
                       PlayerModelGraphPort (via __init__).
Used by: scheduler.tick_scheduler (wired via dependencies_engines.py).
"""

from __future__ import annotations

import logging
from typing import Any

from npc_engine.engines.player_model.player_model_engine import (
    PlayerModelEngine,
    PlayerModelInput,
)
from npc_engine.engines.ports.player_location_read_port import PlayerLocationReadPort
from npc_engine.engines.ports.player_model_port import PlayerModelGraphPort
from npc_engine.engines.ports.relation_read_port import RelationReadPort
from npc_engine.utils.errors import RelationEdgeNotFoundError

# Maximum co-located (npc, player) pairs modelled per scheduler tick — bounds
# graph read/write cost when many NPCs share a location.
MAX_PLAYER_MODEL_CHECKS_PER_TICK: int = 20

_logger = logging.getLogger(__name__)


class PlayerModelTick:
    """Tick adapter wiring PlayerModelEngine into the clock loop.

    On each ``run_tick``: fetch co-located pairs, cap them, and for each pair with
    a RELATES_TO edge derive and upsert the NPC's PlayerModel. No state beyond the
    injected dependencies — safe for concurrent use.
    """

    def __init__(
        self,
        engine: PlayerModelEngine,
        location_reader: PlayerLocationReadPort,
        relation_reader: RelationReadPort,
        model_repo: PlayerModelGraphPort,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            engine: Pure PlayerModelEngine that derives perceived_trust/intent.
            location_reader: PlayerLocationReadPort for co-location queries.
            relation_reader: RelationReadPort for RELATES_TO scalar reads.
            model_repo: PlayerModelGraphPort for upserting derived player models.
        """
        self._engine = engine
        self._location_reader = location_reader
        self._relation_reader = relation_reader
        self._model_repo = model_repo

    async def run_tick(self, tick_id: int) -> dict[str, Any]:
        """Update each co-located NPC's model of the player.

        Args:
            tick_id: Current game tick (stored on each PlayerModel node).
            **_: Swallows the scheduler's session= kwarg during the SEV-24 migration.

        Returns:
            Dict with key ``player_models``: list of serialised PlayerModelUpdate dicts.
        """
        pairs = await self._location_reader.get_collocated_pairs()
        capped = pairs[:MAX_PLAYER_MODEL_CHECKS_PER_TICK]
        updates: list[dict[str, Any]] = []
        for npc_id, player_id in capped:
            update = await self._update_pair(npc_id, player_id, tick_id)
            if update is not None:
                updates.append(update)
        _logger.info(
            "player_model_tick_done",
            extra={"tick_id": tick_id, "pairs_checked": len(capped), "models_updated": len(updates)},
        )
        return {"player_models": updates}

    async def _update_pair(
        self,
        npc_id: str,
        player_id: str,
        tick_id: int,
    ) -> dict[str, Any] | None:
        """Derive and persist one NPC's player model; None when no edge exists."""
        try:
            scalars = await self._relation_reader.get_relation_scalars(
                src_id=npc_id, dst_id=player_id
            )
        except RelationEdgeNotFoundError:
            return None
        update = self._engine.derive(
            PlayerModelInput(
                npc_id=npc_id, player_id=player_id,
                trust=scalars["trust"], fear=scalars["fear"], affection=scalars["affection"],
            )
        )
        await self._model_repo.upsert_player_model(
            npc_id=npc_id, player_id=player_id,
            perceived_trust=update.perceived_trust, perceived_intent=update.perceived_intent,
            tick=tick_id,
        )
        return update.model_dump()
