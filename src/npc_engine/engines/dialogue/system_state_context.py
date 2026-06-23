"""
Module: system_state_context
Layer: engines
Purpose: Engine-resolved live facts bag injected as Tier-0 dialogue context (ISSUE-071).
Does NOT: call graph or LLM services; holds no session.
Dependencies: config.Settings, graph.item_queries, graph.quest_queries (lazy)
Dependencies injected: None (resolve_system_state receives AsyncSession + Settings as params)
Used by: api.routes.dialogue, retrieval.context_builder
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from neo4j import AsyncSession
    from npc_engine.config import Settings

# Minimum item count for an NPC to be considered able to trade.
_MIN_TRADE_ITEM_COUNT: int = 1


class SystemStateContext(BaseModel):
    """Engine-resolved live facts injected into dialogue context as Tier-0.

    Populated by the dialogue route before calling the handler so the NPC's
    generated response is grounded in live engine state rather than graph
    inferences that may be stale. Immutable: populated once per request.

    Attributes:
        npc_can_trade: True when the NPC has at least one tradeable item.
        npc_item_count: Count of NPC-owned tradeable items (0 when cannot trade).
        player_quest_status: Player's active quest status or None if no active quest.
    """

    model_config = ConfigDict(frozen=True)

    npc_can_trade: bool = False
    npc_item_count: int = Field(default=0, ge=0)
    player_quest_status: str | None = None


async def resolve_system_state(
    session: AsyncSession,
    npc_id: str,
    player_id: str | None,
    settings: Settings,
) -> SystemStateContext:
    """Resolve live system state for one NPC+player pair using graph readers.

    Args:
        session: Active Neo4j async session (caller-managed).
        npc_id: NPC character node ID.
        player_id: Player character node ID; when None, quest state is skipped.
        settings: Application settings (unused currently, present for DI symmetry).

    Returns:
        SystemStateContext populated with live engine facts.
    """
    from npc_engine.graph.economy.item_queries import get_items_for_character
    from npc_engine.graph.quest_queries import get_active_quest_for_player

    items = await get_items_for_character(session=session, character_id=npc_id)
    item_count = len(items) if isinstance(items, list) else 0
    can_trade = item_count >= _MIN_TRADE_ITEM_COUNT

    quest_status: str | None = None
    if player_id:
        active_quest = await get_active_quest_for_player(session=session, player_id=player_id)
        if active_quest:
            quest_status = str(active_quest.get("status", ""))

    return SystemStateContext(
        npc_can_trade=can_trade,
        npc_item_count=item_count,
        player_quest_status=quest_status or None,
    )
