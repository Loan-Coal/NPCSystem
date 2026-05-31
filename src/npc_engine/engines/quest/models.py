"""
models.py - Typed quest lifecycle models for engine orchestration.

Does NOT: execute graph writes.

Dependencies injected: None.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QuestObjectiveInput(BaseModel):
    """One quest objective definition with target completion count and graph verification data.

    Attributes:
        objective_id: Stable identifier for this objective.
        target_count: How many times the objective must be satisfied.
        objective_type: Verification strategy — ``"deliver"`` checks HAS_ITEM;
            others are stubs reserved for future phases.
        target_id: Graph node ID the verifier checks against (e.g. item node ID).
    """

    objective_id: str
    target_count: int = Field(ge=1)
    objective_type: Literal["deliver", "kill", "visit", "talk"] = "deliver"
    target_id: str | None = None

    model_config = ConfigDict(frozen=True)


class QuestRewardItem(BaseModel):
    """Item reward payload awarded when a quest completes."""

    item_id: str
    quantity: int = Field(default=1, ge=1)

    model_config = ConfigDict(frozen=True)


class QuestRewardCurrency(BaseModel):
    """Currency reward payload awarded when a quest completes."""

    amount: int = Field(gt=0)

    model_config = ConfigDict(frozen=True)


class QuestTransitionMeta(BaseModel):
    """Audit and idempotency metadata propagated into quest lifecycle events."""

    request_id: str
    actor_id: str
    reason: str
    idempotency_key: str
    idempotency_request_hash: str

    model_config = ConfigDict(frozen=True)


class QuestStateRecord(BaseModel):
    """Canonical persisted quest state for one player and quest pair."""

    quest_id: str
    player_id: str
    reward_source_id: str = "system"
    title: str
    status: str
    objectives: list[QuestObjectiveInput]
    objective_progress: dict[str, int]
    item_rewards: list[QuestRewardItem]
    currency_reward: QuestRewardCurrency | None = None
    rewards_applied: bool = False

    model_config = ConfigDict(frozen=True)
