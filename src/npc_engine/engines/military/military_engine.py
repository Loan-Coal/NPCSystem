"""
Module: military_engine
Layer: engines
Purpose: Per-tick military simulation — resolves battles between opposing armies and
         processes resource yield for controlling factions.
Does NOT: call LLMs or perform graph writes directly (delegated to services).
Dependencies injected: MilitaryGraphPort (via __init__).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import Any

from npc_engine.engines.military.military_battle_service import resolve_battles
from npc_engine.engines.military.military_resource_service import process_resource_yield
from npc_engine.engines.ports.military_port import MilitaryGraphPort

_LOGGER = logging.getLogger(__name__)


class MilitaryEngine:
    """Runs battle resolution and resource yield on every tick."""

    def __init__(self, military_repo: MilitaryGraphPort) -> None:
        """Store the injected military graph port.

        Args:
            military_repo: Military-domain graph reads/writes (MilitaryGraphPort).
        """
        self._military_repo = military_repo

    async def run_tick(self, *, tick_id: int = 0) -> dict[str, Any]:
        """Resolve all active battles and process resource yield.

        Steps:
        1. Detect locations with opposing armies → resolve each battle (strength
           comparison, damage, CONTROLS/OCCUPIES updates, battle Event node).
        2. For each faction controlling a producing location with depletion > 0:
           credit treasury and decrement ResourceNode.depletion.

        Args:
            tick_id: Current game tick ID.
            **_: Swallows the scheduler's ``session=`` kwarg during the SEV-24
                migration (the repository owns sessions now).

        Returns:
            Dict with ``battles_resolved`` count and ``factions_yielded`` count.
        """
        battles = await resolve_battles(self._military_repo, tick_id=tick_id)
        yields = await process_resource_yield(self._military_repo, tick_id=tick_id)

        _LOGGER.info(
            "military_tick_complete",
            extra={
                "tick": tick_id,
                "battles_resolved": len(battles),
                "factions_yielded": len(yields),
            },
        )

        return {
            "battles_resolved": len(battles),
            "factions_yielded": len(yields),
        }
