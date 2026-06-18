"""
replay_helpers.py - Shared idempotent replay query helpers for graph transfer writers.
Layer: graph
Purpose: (auto-detected — review)

Does NOT: validate transfer business rules.

Dependencies injected: AsyncTransaction.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from neo4j import AsyncTransaction


async def load_idempotent_replay_record(
    *,
    tx: AsyncTransaction,
    replay_cypher: str,
    params: Mapping[str, Any],
    idempotency_key: str,
) -> dict[str, Any] | None:
    """Return replay record payload when idempotency key was already applied.

    Args:
        tx: Active Neo4j async transaction used to run the replay query.
        replay_cypher: Cypher query that looks up an existing idempotency record.
        params: Query parameters forwarded to the replay Cypher statement.
        idempotency_key: Client-supplied key; empty string bypasses the lookup.

    Returns:
        Dict of the matched replay record fields, or None if no prior record exists
        or the key is empty.
    """

    if idempotency_key == "":
        return None

    replay_result = await tx.run(replay_cypher, **dict(params))
    replay_record = await replay_result.single()
    if replay_record is None:
        return None
    return dict(replay_record)
