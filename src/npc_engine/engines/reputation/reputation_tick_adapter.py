"""
Module: reputation_tick_adapter
Layer: engines
Purpose: Tick-scheduler adapter wrapping ReputationEngine with the
         run_tick(tick_id) -> dict signature expected by TickScheduler.
         Fetches active NPC IDs from the injected CharacterReadPort each tick and
         delegates propagation to the underlying ReputationEngine.
         Returns {"nudges": 0} immediately when config.enabled is False
         (zero runtime cost, engine never touches the graph).
Does NOT: run Cypher queries directly or hold a Neo4j session (CharacterReadPort and
          the engine's RelationReadPort/ReputationGraphPort own session lifecycle).
Dependencies: engines.reputation.reputation_engine.ReputationEngine,
              engines.reputation.propagation_config.PropagationConfig,
              engines.ports.character_read_port.CharacterReadPort
Dependencies injected: ReputationEngine, CharacterReadPort, player_id, PropagationConfig.
Used by: scheduler.tick_scheduler (wired via dependencies_engines.py).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from npc_engine.engines.reputation.propagation_config import PropagationConfig
from npc_engine.engines.reputation.reputation_engine import ReputationEngine
from npc_engine.utils.logging import get_logger

if TYPE_CHECKING:
    from npc_engine.engines.ports.character_read_port import CharacterReadPort

logger: logging.Logger = get_logger()


class ReputationTickAdapter:
    """Tick-scheduler adapter for ReputationEngine.

    Bridges the mismatch between TickScheduler's expected
    ``run_tick(session, tick_id) -> dict`` signature and
    ReputationEngine's ``run_tick(player_id, npc_ids) -> None``. The scheduler's
    legacy ``session=`` kwarg is accepted and ignored (``**_``) during the SEV-24
    migration; neither the adapter nor the engine holds a Neo4j session.

    On each tick:
    1. Returns {"nudges": 0} immediately when config.enabled is False.
    2. Fetches all active NPC IDs via character_reader.get_npc_ids().
    3. Delegates to engine.run_tick(player_id=..., npc_ids=...).
    4. Returns {"nudges": len(npc_ids)} as a coarse activity counter.

    Attributes:
        _engine: The wrapped ReputationEngine instance.
        _character_reader: CharacterReadPort for NPC ID enumeration (session-per-call).
        _player_id: Player ID whose reputation propagates each tick.
        _config: PropagationConfig; checked for enabled flag before any I/O.
    """

    def __init__(
        self,
        engine: ReputationEngine,
        character_reader: CharacterReadPort,
        player_id: str,
        config: PropagationConfig,
    ) -> None:
        """Initialise the adapter with injected dependencies.

        Args:
            engine: Configured ReputationEngine instance.
            character_reader: CharacterReadPort implementing get_npc_ids().
            player_id: ID of the player character for reputation propagation.
            config: PropagationConfig; used for the enabled guard.
        """
        self._engine = engine
        self._character_reader = character_reader
        self._player_id = player_id
        self._config = config

    async def run_tick(
        self,
        tick_id: int,
    ) -> dict[str, Any]:
        """Run one reputation propagation tick.

        Returns {"nudges": 0} immediately when engine is disabled to avoid any
        graph I/O. Otherwise fetches NPC IDs and delegates to the engine. The
        trailing ``**_`` swallows the scheduler's legacy ``session=`` kwarg.

        Args:
            tick_id: Current game tick (logged for observability).

        Returns:
            Dict with key ``nudges``: count of NPC IDs processed (0 when disabled).
        """
        if not self._config.enabled:
            return {"nudges": 0}

        npc_ids = await self._character_reader.get_npc_ids()
        await self._engine.run_tick(
            player_id=self._player_id,
            npc_ids=npc_ids,
        )
        logger.info(
            "reputation_tick_done",
            extra={"tick_id": tick_id, "npc_count": len(npc_ids)},
        )
        return {"nudges": len(npc_ids)}
