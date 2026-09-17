"""
Module: seed_io
Layer: demo_game (external client)
Purpose: Low-level I/O helpers used by all domain seeders.
         Wraps EngineClient calls with idempotency guards (GET-before-POST).
Dependencies: demo_game.seeds.seed_builders, demo_game.client (TYPE_CHECKING only)
Used by: demo_game.seeds.seed_domain, demo_game.seeds.seed
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from demo_game.seeds.seed_builders import (
    _GAME_TIME,
    _HISTORICAL_GAME_TIME,
    _WORLD_STATE_ID,
    _belief_id,
    _goal_id,
    _memory_id,
    _now,
    _secret_id,
)

if TYPE_CHECKING:
    from demo_game.client import EngineClient

logger = logging.getLogger(__name__)


def _force_patch_world_state(client: EngineClient) -> None:
    """Force-patch world_state epoch and active_conditions to the demo values.

    Called unconditionally after the _seed_node upsert so that a pre-existing
    node with a drifted epoch (e.g. 'age_of_peace') is always corrected.

    Args:
        client: Live EngineClient instance used to reach the HTTP API.
    """
    client.patch_node(
        "world_state",
        _WORLD_STATE_ID,
        {
            "epoch": "war",
            "active_conditions": ["northern_war"],
        },
    )


def _seed_node(
    client: EngineClient,
    node_type: str,
    payload: dict,
) -> str:
    """Upsert a node if it does not already exist.

    Returns:
        "created" or "skipped".
    """
    if client.get_node(node_type, payload["id"]) is not None:
        logger.info("  skip %s/%s (exists)", node_type, payload["id"])
        return "skipped"
    client.upsert_node(node_type, payload)
    logger.info("  created %s/%s", node_type, payload["id"])
    return "created"


def _seed_edge(
    client: EngineClient,
    edge_type: str,
    src_id: str,
    dst_id: str,
    properties: dict | None = None,
) -> str:
    """Upsert an edge if it does not already exist.

    Returns:
        "created" or "skipped".
    """
    if client.get_edge(edge_type, src_id, dst_id) is not None:
        logger.info("  skip edge %s %s→%s (exists)", edge_type, src_id, dst_id)
        return "skipped"
    client.upsert_edge(edge_type, src_id, dst_id, properties)
    logger.info("  created edge %s %s→%s", edge_type, src_id, dst_id)
    return "created"


def _seed_item_edge_if_unowned(
    client: EngineClient,
    owner_id: str,
    item_id: str,
    properties: dict | None = None,
) -> str:
    """Seed OWNS(owner→item) only when no character currently owns the item.

    Unlike _seed_edge, this checks all inbound OWNS edges on the item (not just the
    specific owner→item edge). This prevents re-gifting items that were transferred
    during gameplay — e.g. the player delivers the amulet to Aldric, then reseed
    would otherwise recreate OWNS(player→amulet) because that specific edge no longer
    exists, even though Aldric now owns it.

    Args:
        client: Authenticated EngineClient.
        owner_id: Character ID who should own the item on first seed.
        item_id: Item node ID.
        properties: Optional edge properties (e.g. acquired_at).

    Returns:
        "created" or "skipped".
    """
    current_owners = client.get_graph_edges("OWNS", dst_id=item_id, limit=1)
    if current_owners:
        logger.info("  skip edge OWNS %s→%s (item already owned)", owner_id, item_id)
        return "skipped"
    client.upsert_edge("OWNS", owner_id, item_id, properties or {})
    logger.info("  created edge OWNS %s→%s", owner_id, item_id)
    return "created"


def _seed_memories(
    client: EngineClient,
    npc_id: str,
    memories: list[tuple[str, int, int] | tuple[str, int, int, bool]],
) -> int:
    """Seed an NPC's memories; a 4th tuple element flags a historical (prior-era) memory.

    Args:
        client: Engine client.
        npc_id: Target character node ID.
        memories: (content, vividness, emotional_charge[, is_historical]) tuples.
    Returns:
        Number of memories upserted.
    """
    for n, mem in enumerate(memories):
        is_historical = bool(mem[3]) if len(mem) > 3 else False
        occurred = _HISTORICAL_GAME_TIME if is_historical else None
        client.post_memory(
            npc_id, mem[0], mem[1], mem[2], _GAME_TIME,
            node_id=_memory_id(npc_id, n),
            occurred_at_game_time=occurred,
            is_historical=is_historical,
        )
    return len(memories)


def _seed_npc_inner_life(
    client: EngineClient,
    npc_id: str,
    beliefs: list[tuple[str, int]],
    goals: list[tuple[str, int]],
    memories: list[tuple[str, int, int] | tuple[str, int, int, bool]],
    secret: tuple[str, int],
) -> int:
    """Seed beliefs, goals, memories, and one secret for an NPC.

    Passes stable deterministic IDs to every inner-life item so the underlying
    graph layer uses MERGE semantics. Re-calling this function is idempotent —
    no duplicate nodes are created regardless of prior seed runs.

    Args:
        client: Engine client.
        npc_id: Target character node ID.
        beliefs: List of (content, confidence) tuples.
        goals: List of (description, urgency) tuples.
        memories: List of (content, vividness, emotional_charge) tuples; an optional
            4th bool element marks the memory as historical (a prior-era recollection).
        secret: (content, severity) tuple.

    Returns:
        Number of items upserted.
    """
    created = 0
    for content, confidence in beliefs:
        client.post_belief(npc_id, content, confidence, _GAME_TIME, node_id=_belief_id(npc_id, content))
        created += 1

    for n, (description, urgency) in enumerate(goals):
        client.post_goal(npc_id, description, urgency, _GAME_TIME, node_id=_goal_id(npc_id, n))
        created += 1

    created += _seed_memories(client, npc_id, memories)

    content, severity = secret
    client.post_secret(npc_id, content, severity, _GAME_TIME, node_id=_secret_id(npc_id))
    created += 1

    logger.info("  upserted %d inner-life items for %s", created, npc_id)
    return created
