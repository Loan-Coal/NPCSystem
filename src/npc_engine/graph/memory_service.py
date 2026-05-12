"""
Module: memory_service
Layer: graph
Purpose: Functions for creating Memory nodes, retrieving them, and running vividness decay.
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.memory.memory_engine, npc_engine.retrieval.context_builder
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from neo4j import AsyncSession

from npc_engine.common.json_utils import dump_json
from npc_engine.graph.memory_queries import (
    CYPHER_CREATE_MEMORY,
    CYPHER_DECAY_VIVIDNESS,
    get_memories_for_character,
)
from npc_engine.world.time_utils import TimePoint


async def create_memory(
    session: AsyncSession,
    *,
    character_id: str,
    content: str,
    vividness: int,
    emotional_charge: int,
    game_time: TimePoint,
) -> str:
    """Create a Memory node and link it to a Character via a REMEMBERS edge.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node forming the memory.
        content: Text description of the memorable moment.
        vividness: Initial vividness level (0–100).
        emotional_charge: Emotional intensity (-100–100).
        game_time: Game-time snapshot at which the memory formed.

    Returns:
        Generated UUID string for the new memory node.
    """
    memory_id = str(uuid.uuid4())
    game_time_json = dump_json(
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
            CYPHER_CREATE_MEMORY,
            memory_id=memory_id,
            content=content,
            vividness=vividness,
            emotional_charge=emotional_charge,
            created_at_game_time=game_time_json,
            last_recalled_at=game_time_json,
            character_id=character_id,
            since_game_time=game_time_json,
        )
    return memory_id


async def get_memories_for_character_svc(
    session: AsyncSession,
    *,
    character_id: str,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Fetch top-k memories for a character ordered by vividness descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of memories to return.

    Returns:
        List of memory property dicts sorted by vividness descending.
    """
    return cast(
        list[dict[str, Any]],
        await get_memories_for_character(session, character_id=character_id, k=k),
    )


async def decay_all_vividness(
    session: AsyncSession,
    *,
    decay_per_day: int = 5,
) -> int:
    """Reduce the vividness of all Memory nodes by decay_per_day, clamped to 0.

    Args:
        session: Active Neo4j async session.
        decay_per_day: Amount to subtract from each memory's vividness per day.

    Returns:
        Number of Memory nodes whose vividness was reduced.
    """
    tx = await session.begin_transaction()
    async with tx:
        result = await tx.run(CYPHER_DECAY_VIVIDNESS, decay=decay_per_day)
        record = await result.single()
    return int(record["affected"]) if record else 0
