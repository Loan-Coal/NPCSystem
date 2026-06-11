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
from typing import Any

from neo4j import AsyncSession

from npc_engine.common.json_utils import dump_json
from npc_engine.graph.memory_queries import (
    CYPHER_CREATE_MEMORY,
    CYPHER_DECAY_VIVIDNESS,
    CYPHER_DECAY_VIVIDNESS_WEIGHTED,
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
    node_id: str | None = None,
    occurred_at_game_time: TimePoint | None = None,
    is_historical: bool = False,
) -> str:
    """Create a Memory node and link it to a Character via a REMEMBERS edge.

    Uses MERGE semantics — safe to call multiple times with the same node_id.
    When node_id is None a UUID is auto-generated (legacy behaviour).

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node forming the memory.
        content: Text description of the memorable moment.
        vividness: Initial vividness level (0–100).
        emotional_charge: Emotional intensity (-100–100).
        game_time: Game-time snapshot at which the memory was recorded.
        node_id: Optional caller-supplied stable ID. When provided the node is
            merged on that ID so repeated calls are idempotent. When None a
            UUID is generated.
        occurred_at_game_time: When the remembered event actually happened, distinct
            from the record time (S26.3, DEC-094). Defaults to game_time when None.
        is_historical: True when the memory is of a prior era / long-past event; the
            prompt frames such memories as past, not current.

    Returns:
        The node ID used (either supplied or generated).
    """
    memory_id = node_id if node_id is not None else str(uuid.uuid4())
    game_time_json = _dump_game_time(game_time)
    occurred_json = _dump_game_time(occurred_at_game_time) if occurred_at_game_time is not None else game_time_json
    tx = await session.begin_transaction()
    async with tx:
        await tx.run(
            CYPHER_CREATE_MEMORY,
            memory_id=memory_id,
            content=content,
            vividness=vividness,
            emotional_charge=emotional_charge,
            created_at_game_time=game_time_json,
            occurred_at_game_time=occurred_json,
            is_historical=is_historical,
            last_recalled_at=game_time_json,
            character_id=character_id,
            since_game_time=game_time_json,
        )
    return memory_id


def _dump_game_time(game_time: TimePoint) -> str:
    """Serialize a TimePoint to the canonical game-time JSON string."""
    return dump_json(
        {
            "year": game_time.year,
            "season": game_time.season,
            "day": game_time.day,
            "time_of_day": game_time.time_of_day,
        }
    )


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
    return await get_memories_for_character(session, character_id=character_id, k=k)


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
        await result.consume()
        return int(record["affected"]) if record else 0


async def decay_all_vividness_weighted(
    session: AsyncSession,
    *,
    base_decay: int = 5,
    charge_divisor: int = 20,
) -> int:
    """Reduce vividness using a charge-weighted rate (high emotional_charge → slower decay).

    The per-node decay rate is: max(1, base_decay - floor(emotional_charge / charge_divisor)).
    At emotional_charge=0 the rate equals base_decay; at emotional_charge=80 (with defaults)
    the rate is 1, ensuring traumatic memories persist longer.

    Args:
        session: Active Neo4j async session.
        base_decay: Maximum decay per day applied to low-charge memories.
        charge_divisor: Divisor applied to emotional_charge to compute rate reduction.

    Returns:
        Number of Memory nodes whose vividness was reduced.
    """
    tx = await session.begin_transaction()
    async with tx:
        result = await tx.run(
            CYPHER_DECAY_VIVIDNESS_WEIGHTED,
            base_decay=base_decay,
            charge_divisor=charge_divisor,
        )
        record = await result.single()
        await result.consume()
        return int(record["affected"]) if record else 0


async def delete_memory(
    session: AsyncSession,
    *,
    memory_id: str,
) -> None:
    """Hard-delete a single Memory node and its relationships.

    Args:
        session: Active Neo4j async session.
        memory_id: ID of the Memory node to delete.
    """
    result = await session.run(
        "MATCH (m:Memory {id: $id}) DETACH DELETE m",
        id=memory_id,
    )
    await result.consume()
