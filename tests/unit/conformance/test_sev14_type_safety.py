"""
Regression tests for SEV-14 — type-safety cluster fixes.

Verifies:
1. FrozenApiModel is a real class (not a value alias), so it is valid as a base class.
2. Schema models that inherit FrozenApiModel are proper Pydantic models.
"""

from __future__ import annotations

import inspect


def test_frozen_api_model_is_a_class() -> None:
    """FrozenApiModel must be a class, not a value alias."""
    from npc_engine.api.schemas import FrozenApiModel

    assert inspect.isclass(FrozenApiModel), "FrozenApiModel must be a class"


def test_schema_classes_are_subclasses_of_frozen_api_model() -> None:
    """All schema models must subclass FrozenApiModel (not bypass it)."""
    from npc_engine.api.schemas import (
        ActionReportRequest,
        EmotionResponse,
        FrozenApiModel,
        NPCStateResponse,
        QuestAcceptRequest,
        QuestEvaluateRequest,
        QuestObjectiveBody,
        QuestObjectiveUpdateRequest,
        QuestOfferRequest,
        QuestRewardApplyRequest,
        QuestRewardCurrencyBody,
        QuestRewardItemBody,
    )

    subclasses = [
        NPCStateResponse,
        EmotionResponse,
        ActionReportRequest,
        QuestObjectiveBody,
        QuestRewardItemBody,
        QuestRewardCurrencyBody,
        QuestOfferRequest,
        QuestAcceptRequest,
        QuestObjectiveUpdateRequest,
        QuestEvaluateRequest,
        QuestRewardApplyRequest,
    ]
    for cls in subclasses:
        assert issubclass(cls, FrozenApiModel), f"{cls.__name__} must inherit FrozenApiModel"


def test_schema_models_are_frozen() -> None:
    """Schema models must be immutable (frozen=True enforced by FrozenApiModel)."""
    import pytest
    from pydantic import ValidationError

    from npc_engine.api.schemas import EmotionResponse

    obj = EmotionResponse(npc_id="n1", label="happy", valence=5, arousal=5, updated_at="2026-01-01")
    with pytest.raises((ValidationError, TypeError)):
        obj.npc_id = "mutated"  # type: ignore[misc]
