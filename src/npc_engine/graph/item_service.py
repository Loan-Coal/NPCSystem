"""
Module: item_service
Layer: graph
Purpose: Functions for creating Item nodes, retrieving them, and transferring ownership.
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies: graph.item_queries, common.json_utils, world.time_utils
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.items, npc_engine.retrieval.context_builder,
         npc_engine.engines.dialogue.action_resolver
"""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncSession

from npc_engine.common.json_utils import dump_json
from npc_engine.graph.item_queries import (
    CYPHER_ATTACH_ITEM_OWNER,
    CYPHER_CREATE_ITEM_NODE,
    CYPHER_DETACH_ITEM_OWNER,
    get_item_by_id,
    get_items_for_character,
)
from npc_engine.world.time_utils import TimePoint


async def create_item(
    session: AsyncSession,
    *,
    character_id: str,
    name: str,
    description: str,
    value: int,
    rarity: str,
    type_: str,
    is_unique: bool,
    game_time: TimePoint,
    properties: dict[str, Any] | None = None,
) -> str:
    """Create an Item node and link it to a Character via an OWNS edge.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character who initially owns the item.
        name: Display name of the item.
        description: Freeform description.
        value: Numeric value (e.g. gold pieces).
        rarity: Rarity tier string (common, uncommon, rare, epic, legendary).
        type_: Item category string (weapon, armor, consumable, quest, misc).
        is_unique: Whether this is a unique one-of-a-kind item.
        game_time: Game-time snapshot at which the item was acquired.
        properties: Optional dict of flexible attributes; serialized as JSON.

    Returns:
        Generated UUID string for the new item node.
    """
    item_id = str(uuid.uuid4())
    acquired_at = dump_json(
        {
            "year": game_time.year,
            "season": game_time.season,
            "day": game_time.day,
            "time_of_day": game_time.time_of_day,
        }
    )
    tx = await session.begin_transaction()
    async with tx:
        await tx.run(
            CYPHER_CREATE_ITEM_NODE,
            item_id=item_id,
            name=name,
            description=description,
            value=value,
            rarity=rarity,
            type=type_,
            is_unique="true" if is_unique else "false",
            properties=dump_json(properties) if properties else "",
            character_id=character_id,
            acquired_at=acquired_at,
        )
    return item_id


async def get_items_for_character_svc(
    session: AsyncSession,
    *,
    character_id: str,
) -> list[dict[str, Any]]:
    """Fetch all items owned by a character.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.

    Returns:
        List of item property dicts.
    """
    return await get_items_for_character(session, character_id=character_id)


async def get_item_by_id_svc(
    session: AsyncSession,
    *,
    item_id: str,
) -> dict[str, Any] | None:
    """Fetch a single item by its ID.

    Args:
        session: Active Neo4j async session.
        item_id: ID of the Item node.

    Returns:
        Item property dict, or None if not found.
    """
    return await get_item_by_id(session, item_id=item_id)


async def transfer_ownership(
    session: AsyncSession,
    *,
    item_id: str,
    from_character_id: str,
    to_character_id: str,
    game_time: TimePoint,
) -> None:
    """Transfer ownership of an item from one character to another.

    Deletes the OWNS edge from the source character and creates a new one
    on the destination character. The Item node itself is unchanged.

    Args:
        session: Active Neo4j async session.
        item_id: ID of the Item node to transfer.
        from_character_id: ID of the character currently owning the item.
        to_character_id: ID of the character receiving ownership.
        game_time: Game-time snapshot used as acquired_at on the new edge.
    """
    acquired_at = dump_json(
        {
            "year": game_time.year,
            "season": game_time.season,
            "day": game_time.day,
            "time_of_day": game_time.time_of_day,
        }
    )
    tx = await session.begin_transaction()
    async with tx:
        await tx.run(
            CYPHER_DETACH_ITEM_OWNER,
            character_id=from_character_id,
            item_id=item_id,
        )
        await tx.run(
            CYPHER_ATTACH_ITEM_OWNER,
            character_id=to_character_id,
            item_id=item_id,
            acquired_at=acquired_at,
        )
