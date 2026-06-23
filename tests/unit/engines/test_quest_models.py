"""
Tests for QuestStatus enum and QuestStateRecord model validation.
Layer: engines (test)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from npc_engine.engines.quest.models import QuestStateRecord, QuestStatus


class TestQuestStatusEnum:
    """Verify QuestStatus enum members and str-enum behaviour."""

    def test_quest_status_enum_members(self) -> None:
        """All seven status members exist with correct string values."""
        assert QuestStatus.DRAFT.value == "draft"
        assert QuestStatus.OFFERED.value == "offered"
        assert QuestStatus.ACCEPTED.value == "accepted"
        assert QuestStatus.IN_PROGRESS.value == "in_progress"
        assert QuestStatus.COMPLETED.value == "completed"
        assert QuestStatus.FAILED.value == "failed"
        assert QuestStatus.EXPIRED.value == "expired"

    def test_quest_status_is_str(self) -> None:
        """QuestStatus inherits from str so it serialises cleanly."""
        assert isinstance(QuestStatus.DRAFT, str)
        assert QuestStatus.DRAFT == "draft"

    def test_quest_status_total_count(self) -> None:
        """Exactly seven members — no accidental additions."""
        assert len(QuestStatus) == 7


class TestQuestStateRecordValidation:
    """Verify QuestStateRecord accepts typed and coercible status values."""

    def test_quest_state_record_rejects_invalid_status(self) -> None:
        """A completely invalid status string must raise ValidationError."""
        with pytest.raises((ValidationError, Exception)):
            QuestStateRecord(
                quest_id="q1",
                player_id="p1",
                title="t",
                status="invalid",
                objectives=[],
                objective_progress={},
                item_rewards=[],
            )

    def test_quest_state_record_accepts_enum_status(self) -> None:
        """Constructing with a QuestStatus enum member works and round-trips."""
        rec = QuestStateRecord(
            quest_id="q1",
            player_id="p1",
            title="t",
            status=QuestStatus.OFFERED,
            objectives=[],
            objective_progress={},
            item_rewards=[],
        )
        assert rec.status == QuestStatus.OFFERED

    def test_quest_state_record_coerces_valid_string(self) -> None:
        """A raw valid string is coerced to the matching QuestStatus member."""
        rec = QuestStateRecord(
            quest_id="q1",
            player_id="p1",
            title="t",
            status="offered",
            objectives=[],
            objective_progress={},
            item_rewards=[],
        )
        assert rec.status == QuestStatus.OFFERED
        assert isinstance(rec.status, QuestStatus)

    def test_quest_state_record_accepts_failed_status(self) -> None:
        """New FAILED state is accepted by QuestStateRecord."""
        rec = QuestStateRecord(
            quest_id="q1",
            player_id="p1",
            title="t",
            status=QuestStatus.FAILED,
            objectives=[],
            objective_progress={},
            item_rewards=[],
        )
        assert rec.status == QuestStatus.FAILED

    def test_quest_state_record_accepts_expired_status(self) -> None:
        """New EXPIRED state is accepted by QuestStateRecord."""
        rec = QuestStateRecord(
            quest_id="q1",
            player_id="p1",
            title="t",
            status=QuestStatus.EXPIRED,
            objectives=[],
            objective_progress={},
            item_rewards=[],
        )
        assert rec.status == QuestStatus.EXPIRED
