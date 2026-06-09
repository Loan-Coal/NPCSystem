"""
Module: proactive_memory_reader
Layer: graph
Purpose: Read-only Cypher accessor that fetches unshared memories for an NPC,
         implementing MemoryServiceProtocol from the proactive dialogue engine.
         Uses REMEMBERS edges, ordered by vividness DESC, limited to k rows.
Known limitation: memory.yaml has no 'shared' field; every returned memory has
         shared=False in this slice (EXP-10 slice-2 schema waiver).
Dependencies: neo4j.AsyncSession
Dependencies injected: AsyncSession (per call — no constructor args required).
Used by: engines.proactive_dialogue.proactive_tick_adapter
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_GET_UNSHARED_MEMORIES = """
MATCH (c:Character {id: $character_id})-[:REMEMBERS]->(m:Memory)
RETURN m.id AS memory_id,
       m.content AS content,
       toInteger(m.vividness) AS vividness
ORDER BY m.vividness DESC
LIMIT $k
"""


class ProactiveMemoryReader:
    """Read-only graph accessor for NPC memories ordered by vividness.

    Implements MemoryServiceProtocol — stateless, no constructor dependencies.

    Known limitation (EXP-10 slice-2 schema waiver): memory.yaml has no
    ``shared`` field; every returned memory dict carries ``shared=False``.
    This will be updated once the schema gains that field.
    """

    async def get_unshared_memories(
        self,
        session: AsyncSession,
        *,
        npc_id: str,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """Return up to k memories for an NPC, ordered by vividness DESC.

        Because the Memory node schema has no ``shared`` field at this point
        (EXP-10 slice-2 waiver), every returned row is injected with
        ``shared: False`` to satisfy the MemoryServiceProtocol contract.

        Args:
            session: Active Neo4j async session.
            npc_id: Character ID to query.
            k: Maximum memories to return.

        Returns:
            List of dicts with keys: memory_id, content, vividness, shared.
        """
        result = await session.run(
            CYPHER_GET_UNSHARED_MEMORIES,
            character_id=npc_id,
            k=k,
        )
        try:
            rows: list[dict[str, Any]] = [
                {
                    "memory_id": record["memory_id"],
                    "content": record["content"],
                    "vividness": record["vividness"],
                    "shared": False,  # schema waiver: no shared field in memory.yaml
                }
                async for record in result
            ]
        finally:
            await result.consume()
        return rows
