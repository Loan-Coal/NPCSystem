"""
Module: pair_selector
Layer: engines/gossip
Purpose: Selects gossip-eligible NPC pairs with faction-weighted deterministic ordering.
Does NOT: mutate knowledge edges.
Dependencies injected: GossipGraphPort.
Used by: npc_engine.engines.gossip.gossip_handler.GossipHandler.run_tick.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from npc_engine.engines.gossip.gossip_config import GossipWeightConfig
from npc_engine.engines.gossip.pair_weighting import compute_faction_weight

if TYPE_CHECKING:
    from npc_engine.engines.ports.gossip_port import GossipGraphPort

_GOAL_ALIGNMENT_BONUS = 10


def _pair_weight(character: dict[str, Any]) -> int:
    return int(character.get("gossipy", 50))


async def _fetch_goal_target_ids(repo: GossipGraphPort, character_id: str) -> set[str]:
    """Return the set of non-empty target_id values from this character's active goals.

    Args:
        repo: Gossip graph port providing goal queries.
        character_id: Character node ID to query goals for.

    Returns:
        Set of target_id strings (empty strings excluded).
    """
    goals = await repo.get_goals_for_character(character_id, k=20, status_filter="active")
    return {g["target_id"] for g in goals if g.get("target_id")}


async def _fetch_known_node_ids(repo: GossipGraphPort, character_id: str) -> set[str]:
    """Delegate to graph port: returns node IDs known by character via KNOWS_ABOUT."""
    return await repo.fetch_known_node_ids(character_id)


async def select_pairs(
    repo: GossipGraphPort,
    max_pairs: int,
    weight_config: GossipWeightConfig,
) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]]:
    """Return top-weighted directed gossip pairs sorted deterministically.

    Pairs are all co-located active non-player NPC combinations. Ranking uses
    the sum of both characters' ``gossipy`` attributes multiplied by the faction
    weight as the primary key, with an optional +10 goal-alignment bonus when
    either NPC has an active goal whose ``target_id`` matches a node known to
    the other NPC. Character IDs serve as tiebreakers.

    Args:
        repo: Gossip graph port providing pair and goal reads.
        max_pairs: Maximum number of pairs to return.
        weight_config: Faction weight multipliers for pair ranking.

    Returns:
        List of (sharer, receiver, location, faction_ctx) tuples, limited to max_pairs.
        faction_ctx contains ``a_faction_ids``, ``b_faction_ids``, and ``best_standing``.
    """
    rows = await repo.fetch_gossip_pairs()

    # Build goal-alignment bonus map — skip entirely when no rows
    goal_alignment: dict[tuple[str, str], int] = {}
    if rows:
        unique_ids: set[str] = set()
        for row in rows:
            unique_ids.add(row["a"]["id"])
            unique_ids.add(row["b"]["id"])

        goal_targets: dict[str, set[str]] = {}
        known_nodes: dict[str, set[str]] = {}
        any_goals = False
        for npc_id in unique_ids:
            targets = await _fetch_goal_target_ids(repo, npc_id)
            goal_targets[npc_id] = targets
            if targets:
                any_goals = True

        if any_goals:
            for npc_id in unique_ids:
                known_nodes[npc_id] = await _fetch_known_node_ids(repo, npc_id)

            for row in rows:
                a_id = row["a"]["id"]
                b_id = row["b"]["id"]
                bonus = 0
                if goal_targets[a_id] & known_nodes.get(b_id, set()):
                    bonus += _GOAL_ALIGNMENT_BONUS
                if goal_targets[b_id] & known_nodes.get(a_id, set()):
                    bonus += _GOAL_ALIGNMENT_BONUS
                if bonus:
                    goal_alignment[(a_id, b_id)] = bonus

    def _sort_key(row: dict[str, Any]) -> tuple[float, str, str]:
        a_id = row["a"]["id"]
        b_id = row["b"]["id"]
        base = _pair_weight(row["a"]) + _pair_weight(row["b"])
        faction_weight = compute_faction_weight(
            sharer_faction_ids=set(row["a_faction_ids"]),
            receiver_faction_ids=set(row["b_faction_ids"]),
            best_standing=row["best_standing"],
            same_faction_boost=weight_config.same_faction_boost,
            allied_boost=weight_config.allied_boost,
            hostile_penalty=weight_config.hostile_penalty,
        )
        alignment_bonus = goal_alignment.get((a_id, b_id), 0)
        return (base * faction_weight + alignment_bonus, a_id, b_id)

    ranked = sorted(rows, key=_sort_key, reverse=True)
    return [
        (
            row["a"],
            row["b"],
            row["loc"],
            {
                "a_faction_ids": row["a_faction_ids"],
                "b_faction_ids": row["b_faction_ids"],
                "best_standing": row["best_standing"],
            },
        )
        for row in ranked[:max_pairs]
    ]
