"""
test_quest_lifecycle_integration_v14.py - Integration tests for P3 quest lifecycle writes.

Does NOT: validate HTTP route wiring.

Dependencies injected: Neo4j test environment via env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.config import Settings
from npc_engine.engines.quest.models import QuestObjectiveInput, QuestTransitionMeta
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine


def _meta(request_suffix: str) -> QuestTransitionMeta:
    return QuestTransitionMeta(
        request_id=f"req-{request_suffix}",
        actor_id="player-integration",
        reason="integration",
        idempotency_key=f"idem-{request_suffix}",
        idempotency_request_hash=f"hash-{request_suffix}",
    )


@pytest.mark.asyncio
async def test_quest_lifecycle_offer_to_completion_and_rewards() -> None:
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD are required")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        settings = Settings(API_KEY_SECRET="local_dev_secret_change_this_2026")
        engine = QuestLifecycleEngine(settings=settings)
        quest_id = f"quest-int-{uuid4()}"
        player_id = f"player-int-{uuid4()}"

        async with driver.session() as session:
            offered = await engine.offer_quest(
                session=session,
                quest_id=quest_id,
                player_id=player_id,
                title="Integration quest",
                objectives=[QuestObjectiveInput(objective_id="obj-1", target_count=1)],
                item_rewards=[],
                currency_reward=None,
                meta=_meta("offer"),
            )
            assert offered["status"] == "offered"

            accepted = await engine.accept_quest(
                session=session,
                quest_id=quest_id,
                player_id=player_id,
                meta=_meta("accept"),
            )
            assert accepted["status"] == "accepted"

            in_progress = await engine.update_objective(
                session=session,
                quest_id=quest_id,
                player_id=player_id,
                objective_id="obj-1",
                progress_delta=1,
                meta=_meta("update"),
            )
            assert in_progress["status"] == "in_progress"

            completed = await engine.evaluate_completion(
                session=session,
                quest_id=quest_id,
                player_id=player_id,
                meta=_meta("evaluate"),
            )
            assert completed["status"] == "completed"

            rewarded = await engine.apply_rewards(
                session=session,
                quest_id=quest_id,
                player_id=player_id,
                meta=_meta("reward"),
            )
            assert rewarded["rewards_applied"] is True
    finally:
        await driver.close()
