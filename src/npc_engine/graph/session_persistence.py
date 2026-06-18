"""
Module: session_persistence
Layer: graph
Purpose: Save and load dialogue session turns as first-class `dialogue_turn` nodes in
         Neo4j (DEC-106 / F3.5). One node per turn, property-anchored by (npc_id, player_id)
         and ordered by turn_index — replacing the per-player JSON-blob Character properties
         (which collided distinct player ids, OQ-9, and were not queryable/orderable/prunable).
Does NOT: manage transactions, call LLMs, import from the engines layer, apply TTL logic,
          or raise errors on save — callers handle error policy.
Dependencies: neo4j.AsyncSession, logging
Dependencies injected: AsyncSession (per call — stateless, no constructor state).
Used by: engines/dialogue/session_store (SessionStore.save_to_graph / load_from_graph).
"""

from __future__ import annotations

from typing import Any
import logging

from neo4j import AsyncSession

_logger = logging.getLogger(__name__)

# Graph label for a single persisted dialogue turn (node_type: dialogue_turn).
DIALOGUE_TURN_LABEL = "DialogueTurn"

# Separator between a turn's role and its content (turns are stored as "role: content").
_TURN_SEPARATOR = ": "

_CYPHER_DELETE_PAIR_TURNS = """\
MATCH (t:DialogueTurn {npc_id: $npc_id, player_id: $player_id})
DETACH DELETE t
"""

_CYPHER_CREATE_TURNS = """\
UNWIND $rows AS row
CREATE (t:DialogueTurn {
    id: row.id, npc_id: $npc_id, player_id: $player_id,
    turn_index: row.turn_index, role: row.role, content: row.content, tick: row.turn_index
})
"""

_CYPHER_READ_ALL_TURNS = """\
MATCH (t:DialogueTurn)
RETURN t.npc_id AS npc_id, t.player_id AS player_id,
       t.turn_index AS turn_index, t.role AS role, t.content AS content
ORDER BY t.npc_id, t.player_id, t.turn_index
"""


def _split_turn(turn: str) -> tuple[str, str]:
    """Split a "role: content" turn string into (role, content); no separator → ("", turn)."""
    if _TURN_SEPARATOR in turn:
        role, content = turn.split(_TURN_SEPARATOR, 1)
        return role, content
    return "", turn


def _join_turn(role: str, content: str) -> str:
    """Inverse of _split_turn: rejoin (role, content) into the original turn string."""
    if role:
        return f"{role}{_TURN_SEPARATOR}{content}"
    return content


async def write_session_turns(
    session: AsyncSession,
    npc_id: str,
    player_id: str,
    turns: list[str],
) -> None:
    """Replace the (npc_id, player_id) dialogue turns with one dialogue_turn node per turn.

    Deletes the pair's existing dialogue_turn nodes then creates the capped list anew, so the
    write is idempotent and ordered by turn_index. Distinct player ids never collide (each turn
    is its own node with a player_id property — no dynamic Character property keys).

    Args:
        session: Active Neo4j async session.
        npc_id: NPC identifier stored on each dialogue_turn node.
        player_id: Player identifier stored on each dialogue_turn node.
        turns: Ordered list of "role: content" turn strings to persist.

    Raises:
        Any Neo4j driver exception — callers are responsible for swallowing on shutdown.
    """
    del_result = await session.run(_CYPHER_DELETE_PAIR_TURNS, npc_id=npc_id, player_id=player_id)
    await del_result.consume()
    rows = []
    for index, turn in enumerate(turns):
        role, content = _split_turn(turn)
        rows.append({
            "id": f"{npc_id}__{player_id}__{index}",
            "turn_index": index, "role": role, "content": content,
        })
    if rows:
        result = await session.run(_CYPHER_CREATE_TURNS, npc_id=npc_id, player_id=player_id, rows=rows)
        await result.consume()


async def read_all_session_turns(session: AsyncSession) -> list[dict[str, Any]]:
    """Read all persisted dialogue_turn nodes, grouped per (npc_id, player_id), ordered by turn_index.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of dicts with keys ``npc_id`` (str), ``player_id`` (str), and ``turns`` (list[str],
        each reconstructed as the original "role: content" string). May be empty.
    """
    result = await session.run(_CYPHER_READ_ALL_TURNS)
    ordered: dict[tuple[str, str], list[str]] = {}
    async for record in result:
        npc_id = record["npc_id"]
        player_id = record["player_id"]
        if not npc_id or not player_id:
            continue
        turn = _join_turn(record["role"] or "", record["content"] or "")
        ordered.setdefault((npc_id, player_id), []).append(turn)
    return [
        {"npc_id": npc_id, "player_id": player_id, "turns": turns}
        for (npc_id, player_id), turns in ordered.items()
    ]
