"""
quest_writer.py - Quest state persistence helpers for lifecycle engine.

Does NOT: enforce quest transition policies.

Dependencies injected: AsyncSession or AsyncTransaction.
"""

from __future__ import annotations

import json

from neo4j import AsyncSession, AsyncTransaction


QuestGraphRunner = AsyncSession | AsyncTransaction


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


def _record_to_state_payload(record) -> dict:
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


async def get_quest_state(*, session: QuestGraphRunner, quest_id: str, player_id: str) -> dict | None:
    """Read one persisted quest state for a quest and player pair."""

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
    state_payload: dict,
) -> dict:
    """Create quest state once, then return the current stored payload without overwriting."""

    currency_reward = state_payload.get("currency_reward")
    currency_reward_json = None if currency_reward is None else json.dumps(currency_reward)

    result = await session.run(
        CYPHER_CREATE_QUEST_STATE_IF_ABSENT,
        id=f"{quest_id}:{player_id}",
        quest_id=state_payload["quest_id"],
        player_id=state_payload["player_id"],
        reward_source_id=state_payload["reward_source_id"],
        title=state_payload["title"],
        status=state_payload["status"],
        objectives_json=json.dumps(state_payload["objectives"]),
        objective_progress_json=json.dumps(state_payload["objective_progress"]),
        item_rewards_json=json.dumps(state_payload["item_rewards"]),
        currency_reward_json=currency_reward_json,
        rewards_applied=state_payload["rewards_applied"],
    )
    record = await result.single()
    assert record is not None
    return _record_to_state_payload(record)


async def upsert_quest_state(
    *,
    session: QuestGraphRunner,
    quest_id: str,
    player_id: str,
    state_payload: dict,
) -> dict:
    """Persist one quest state payload and return the same canonical payload."""

    currency_reward = state_payload.get("currency_reward")
    currency_reward_json = None if currency_reward is None else json.dumps(currency_reward)

    result = await session.run(
        CYPHER_MERGE_QUEST_STATE,
        id=f"{quest_id}:{player_id}",
        quest_id=state_payload["quest_id"],
        player_id=state_payload["player_id"],
        reward_source_id=state_payload["reward_source_id"],
        title=state_payload["title"],
        status=state_payload["status"],
        objectives_json=json.dumps(state_payload["objectives"]),
        objective_progress_json=json.dumps(state_payload["objective_progress"]),
        item_rewards_json=json.dumps(state_payload["item_rewards"]),
        currency_reward_json=currency_reward_json,
        rewards_applied=state_payload["rewards_applied"],
    )
    await result.consume()

    return {
        "quest_id": state_payload["quest_id"],
        "player_id": state_payload["player_id"],
        "reward_source_id": state_payload["reward_source_id"],
        "title": state_payload["title"],
        "status": state_payload["status"],
        "objectives": list(state_payload["objectives"]),
        "objective_progress": dict(state_payload["objective_progress"]),
        "item_rewards": list(state_payload["item_rewards"]),
        "currency_reward": currency_reward,
        "rewards_applied": bool(state_payload["rewards_applied"]),
    }
