"""
Module: session_persistence
Layer: graph
Purpose: Save and load dialogue session turn blobs on Character nodes in Neo4j.
Does NOT: manage transactions, call LLMs, import from the engines layer,
          apply TTL logic, or raise errors on save — callers handle error policy.
Dependencies: neo4j.AsyncSession, json, logging
Dependencies injected: AsyncSession (per call — stateless, no constructor state).
Used by: engines/dialogue/session_store (SessionStore.save_to_graph / load_from_graph).
"""

from __future__ import annotations

import json
import logging

from neo4j import AsyncSession

_logger = logging.getLogger(__name__)

_SESSION_PROP_PREFIX = "session_turns_"

_CYPHER_UPSERT_SESSION = """\
MERGE (c:Character {id: $npc_id})
SET c[$prop_key] = $turns_json,
    c.session_turns_updated_at = datetime()
"""

_CYPHER_READ_ALL_SESSIONS = """\
MATCH (c:Character)
WHERE any(key IN keys(c) WHERE key STARTS WITH 'session_turns_')
RETURN c
"""


def make_prop_key(player_id: str) -> str:
    """Build the Character-node property key for a player's session turns.

    Sanitises ``player_id`` by replacing characters that are invalid in Neo4j
    dynamic property keys with underscores.

    Args:
        player_id: Raw player identifier string.

    Returns:
        Property key string of the form ``session_turns_<sanitised_player_id>``.
    """
    safe = player_id.replace(":", "_").replace("-", "_")
    return f"{_SESSION_PROP_PREFIX}{safe}"


async def write_session_turns(
    session: AsyncSession,
    npc_id: str,
    player_id: str,
    turns: list[str],
) -> None:
    """Write a session turn list as a JSON blob onto a Character node.

    Uses MERGE so the write is idempotent — a missing Character node is created
    with only the turns property set (the graph seed should normally create it first).

    Args:
        session: Active Neo4j async session.
        npc_id: NPC identifier; used as Character node ``id``.
        player_id: Player identifier; used to build the dynamic property key.
        turns: Ordered list of turn strings to persist.

    Raises:
        Any Neo4j driver exception — callers are responsible for swallowing on shutdown.
    """
    prop_key = make_prop_key(player_id)
    turns_json = json.dumps(turns)
    result = await session.run(
        _CYPHER_UPSERT_SESSION,
        npc_id=npc_id,
        prop_key=prop_key,
        turns_json=turns_json,
    )
    await result.consume()


async def read_all_session_turns(session: AsyncSession) -> list[dict]:
    """Read all persisted session turn blobs from Character nodes.

    Returns a flat list of records, each containing ``npc_id``, ``player_id``,
    and ``turns`` (decoded from JSON).  Invalid JSON values are logged and skipped.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of dicts with keys ``npc_id`` (str), ``player_id`` (str), and
        ``turns`` (list[str]).  May be empty if no sessions are persisted.
    """
    result = await session.run(_CYPHER_READ_ALL_SESSIONS)
    records: list[dict] = []
    async for record in result:
        node = record["c"]
        props: dict = dict(node)
        npc_id: str | None = props.get("id")
        if not npc_id:
            continue
        for key, value in props.items():
            if not key.startswith(_SESSION_PROP_PREFIX):
                continue
            player_key = key[len(_SESSION_PROP_PREFIX):]
            if not player_key or value is None:
                continue
            try:
                turns: list[str] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                _logger.warning(
                    "session_persistence.load_bad_json",
                    extra={"npc_id": npc_id, "key": key},
                )
                continue
            records.append(
                {"npc_id": npc_id, "player_id": player_key, "turns": turns}
            )
    return records
