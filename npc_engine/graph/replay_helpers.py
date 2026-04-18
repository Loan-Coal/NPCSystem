"""
replay_helpers.py - Shared idempotent replay query helpers for graph transfer writers.

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
    """Return replay record payload when idempotency key was already applied."""

    if idempotency_key == "":
        return None

    replay_result = await tx.run(replay_cypher, **dict(params))
    replay_record = await replay_result.single()
    if replay_record is None:
        return None
    return dict(replay_record)
