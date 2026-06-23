"""
quest_writer.py - Quest state persistence helpers for lifecycle engine.
Layer: graph
Purpose: Quest state persistence helpers for lifecycle engine.

Does NOT: enforce quest transition policies.

Dependencies injected: AsyncSession or AsyncTransaction.
"""

from __future__ import annotations

from typing import Any
import json

from neo4j import AsyncSession, AsyncTransaction, Record


QuestGraphRunner = AsyncSession | AsyncTransaction


CYPHER_UPDATE_QUEST_NODE_STATUS = """
MATCH (q:Quest {id: $quest_id})
SET q.status = $status,
    q.updated_at = datetime()
"""


CYPHER_GET_QUEST_STATE = """
MATCH (q:QuestState {id: $id})
RETURN q.quest_id AS quest_id,
       q.player_id AS player_id,
       q.reward_source_id AS reward_source_id,
       q.title AS title,
       q.status AS status,
       coalesce(q.objectives_json, '[]') AS objectives_json,
       coalesce(q.objective_progress_json, '{}') AS objective_progress_json,
       coalesce(q.item_rewards_json, '[]') AS item_rewards_json,
       q.currency_reward_json AS currency_reward_json,
       coalesce(q.rewards_applied, false) AS rewards_applied
LIMIT 1
"""


CYPHER_MERGE_QUEST_STATE = """
MERGE (q:QuestState {id: $id})
ON CREATE SET q.created_at = datetime()
SET q.quest_id = $quest_id,
    q.player_id = $player_id,
    q.reward_source_id = $reward_source_id,
    q.title = $title,
    q.status = $status,
    q.objectives_json = $objectives_json,
    q.objective_progress_json = $objective_progress_json,
    q.item_rewards_json = $item_rewards_json,
    q.currency_reward_json = $currency_reward_json,
    q.rewards_applied = $rewards_applied,
    q.updated_at = datetime()
"""


CYPHER_CREATE_QUEST_STATE_IF_ABSENT = """
MERGE (q:QuestState {id: $id})
ON CREATE SET q.quest_id = $quest_id,
              q.player_id = $player_id,
              q.reward_source_id = $reward_source_id,
              q.title = $title,
              q.status = $status,
              q.objectives_json = $objectives_json,
              q.objective_progress_json = $objective_progress_json,
              q.item_rewards_json = $item_rewards_json,
              q.currency_reward_json = $currency_reward_json,
              q.rewards_applied = $rewards_applied,
              q.updated_at = datetime(),
              q.created_at = datetime()
RETURN q.quest_id AS quest_id,
       q.player_id AS player_id,
       q.reward_source_id AS reward_source_id,
       q.title AS title,
       q.status AS status,
       coalesce(q.objectives_json, '[]') AS objectives_json,
       coalesce(q.objective_progress_json, '{}') AS objective_progress_json,
       coalesce(q.item_rewards_json, '[]') AS item_rewards_json,
       q.currency_reward_json AS currency_reward_json,
       coalesce(q.rewards_applied, false) AS rewards_applied
"""


def _record_to_state_payload(record: Record) -> dict[str, Any]:
    currency_reward_json = record["currency_reward_json"]
    currency_reward = None
    if currency_reward_json is not None and str(currency_reward_json).strip() != "":
        currency_reward = json.loads(str(currency_reward_json))

    return {
        "quest_id": str(record["quest_id"]),
        "player_id": str(record["player_id"]),
        "reward_source_id": str(record["reward_source_id"]),
        "title": str(record["title"]),
        "status": str(record["status"]),
        "objectives": json.loads(str(record["objectives_json"])),
        "objective_progress": json.loads(str(record["objective_progress_json"])),
        "item_rewards": json.loads(str(record["item_rewards_json"])),
        "currency_reward": currency_reward,
        "rewards_applied": bool(record["rewards_applied"]),
    }


def _state_write_params(*, quest_id: str, player_id: str, state_payload: dict[str, Any]) -> dict[str, Any]:
    """Serialize quest payload into query parameters for persistence writes."""

    currency_reward = state_payload.get("currency_reward")
    return {
        "id": f"{quest_id}:{player_id}",
        "quest_id": state_payload["quest_id"],
        "player_id": state_payload["player_id"],
        "reward_source_id": state_payload["reward_source_id"],
        "title": state_payload["title"],
        "status": state_payload["status"],
        "objectives_json": json.dumps(state_payload["objectives"]),
        "objective_progress_json": json.dumps(state_payload["objective_progress"]),
        "item_rewards_json": json.dumps(state_payload["item_rewards"]),
        "currency_reward_json": None if currency_reward is None else json.dumps(currency_reward),
        "rewards_applied": state_payload["rewards_applied"],
    }


def _deep_copy_json(value: object) -> object:
    """Return a detached JSON-compatible copy for immutable return payloads."""

    return json.loads(json.dumps(value))


def _canonical_state_payload(state_payload: dict[str, Any]) -> dict[str, Any]:
    """Build detached canonical quest payload for callers."""

    currency_reward = state_payload.get("currency_reward")
    return {
        "quest_id": str(state_payload["quest_id"]),
        "player_id": str(state_payload["player_id"]),
        "reward_source_id": str(state_payload["reward_source_id"]),
        "title": str(state_payload["title"]),
        "status": str(state_payload["status"]),
        "objectives": _deep_copy_json(state_payload["objectives"]),
        "objective_progress": _deep_copy_json(state_payload["objective_progress"]),
        "item_rewards": _deep_copy_json(state_payload["item_rewards"]),
        "currency_reward": None if currency_reward is None else _deep_copy_json(currency_reward),
        "rewards_applied": bool(state_payload["rewards_applied"]),
    }


async def update_quest_node_status(
    *,
    session: QuestGraphRunner,
    quest_id: str,
    status: str,
) -> None:
    """Write a lifecycle status back to the Quest node for context-builder queries.

    This keeps the Quest node's ``status`` field in sync with QuestState so that
    graph reads used for NPC context injection reflect the current lifecycle state.

    Args:
        session: Active Neo4j session or transaction.
        quest_id: ID of the Quest node to update.
        status: New lifecycle status string (e.g. ``"accepted"``, ``"completed"``).
    """
    result = await session.run(CYPHER_UPDATE_QUEST_NODE_STATUS, quest_id=quest_id, status=status)
    await result.consume()


async def get_quest_state(*, session: QuestGraphRunner, quest_id: str, player_id: str) -> dict[str, Any] | None:
    """Read one persisted quest state for a quest and player pair.

    Args:
        session: Active Neo4j session or transaction used to run the read query.
        quest_id: Identifier of the quest definition.
        player_id: ID of the player character whose state is requested.

    Returns:
        Dict with deserialized quest state fields, or None if no record exists.
    """

    result = await session.run(CYPHER_GET_QUEST_STATE, id=f"{quest_id}:{player_id}")
    record = await result.single()
    if record is None:
        return None

    return _record_to_state_payload(record)


async def create_quest_state_if_absent(
    *,
    session: QuestGraphRunner,
    quest_id: str,
    player_id: str,
    state_payload: dict[str, Any],
) -> dict[str, Any]:
    """Create quest state once, then return the current stored payload without overwriting.

    Args:
        session: Active Neo4j session or transaction used to run the merge query.
        quest_id: Identifier of the quest definition.
        player_id: ID of the player character whose state is being initialized.
        state_payload: Initial quest state dict[str, Any] to persist if no record exists yet.

    Returns:
        Dict with the current stored quest state fields (may differ from state_payload if record existed).
    """
    write_params = _state_write_params(quest_id=quest_id, player_id=player_id, state_payload=state_payload)

    result = await session.run(
        CYPHER_CREATE_QUEST_STATE_IF_ABSENT,
        **write_params,
    )
    record = await result.single()
    assert record is not None
    return _record_to_state_payload(record)


async def upsert_quest_state(
    *,
    session: QuestGraphRunner,
    quest_id: str,
    player_id: str,
    state_payload: dict[str, Any],
) -> dict[str, Any]:
    """Persist one quest state payload and return the same canonical payload.

    Args:
        session: Active Neo4j session or transaction used to run the merge query.
        quest_id: Identifier of the quest definition.
        player_id: ID of the player character whose state is being persisted.
        state_payload: Full quest state dict[str, Any] to write; replaces any existing record.

    Returns:
        Detached canonical dict[str, Any] with the same data that was written (deep-copied for immutability).
    """
    write_params = _state_write_params(quest_id=quest_id, player_id=player_id, state_payload=state_payload)

    result = await session.run(
        CYPHER_MERGE_QUEST_STATE,
        **write_params,
    )
    await result.consume()

    return _canonical_state_payload(state_payload)
