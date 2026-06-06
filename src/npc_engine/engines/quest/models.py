"""
Module: models
Layer: engines
Purpose: Typed quest lifecycle models for engine orchestration, including the
    QuestStatus enum and QuestStateRecord for per-player quest state.
Dependencies: pydantic, enum (stdlib only).
Used by: engines/quest/quest_lifecycle_engine.py, api quest routes.

Does NOT: execute graph writes.
"""

from __future__ import annotations

import enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QuestStatus(str, enum.Enum):
    """Valid lifecycle states for a quest.

    Inherits from ``str`` so Pydantic v2 serialises the value without a
    custom validator, and Neo4j receives a plain string via ``.value``.

    Members:
        DRAFT: Quest generated but not yet offered to any player.
        OFFERED: Quest presented to a specific player, awaiting acceptance.
        ACCEPTED: Player accepted the quest; objectives not yet started.
        IN_PROGRESS: At least one objective has been updated.
        COMPLETED: All objectives met; rewards pending or applied.
        FAILED: Quest ended without completion (slice-2 adds transition logic).
        EXPIRED: Quest timed out before player could complete it (slice-2).
    """

    DRAFT = "draft"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


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
    """Canonical persisted quest state for one player and quest pair.

    The ``status`` field uses ``QuestStatus`` (a ``str``-based enum).
    Pydantic v2 coerces valid raw strings automatically, so callers that
    pass ``status="offered"`` continue to work without modification.
    """

    quest_id: str
    player_id: str
    reward_source_id: str = "system"
    title: str
    status: QuestStatus
    objectives: list[QuestObjectiveInput]
    objective_progress: dict[str, int]
    item_rewards: list[QuestRewardItem]
    currency_reward: QuestRewardCurrency | None = None
    rewards_applied: bool = False

    model_config = ConfigDict(frozen=True)
