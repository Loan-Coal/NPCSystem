"""
test_quest_verifier.py - Unit tests for VisitVerifier, KillVerifier, TalkVerifier.

Does NOT: execute real Neo4j reads.

Dependencies injected: mock InteractionGraphPort returning controlled counts (SEV-24).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.interaction.quest_verifier import (
    KillVerifier,
    TalkVerifier,
    VisitVerifier,
    verify_objectives,
)
from npc_engine.engines.quest.models import QuestObjectiveInput


# ---------------------------------------------------------------------------
# Fake InteractionGraphPort infrastructure
# ---------------------------------------------------------------------------


def _repo(**counts: int) -> MagicMock:
    """Return a mock port whose count_* methods return the supplied values (default 0)."""
    repo = MagicMock()
    for name in (
        "count_player_has_item",
        "count_player_located_at",
        "count_player_was_at",
        "count_target_inactive",
        "count_player_co_located_with",
    ):
        setattr(repo, name, AsyncMock(return_value=counts.get(name, 0)))
    return repo


# ---------------------------------------------------------------------------
# VisitVerifier
# ---------------------------------------------------------------------------


class TestVisitVerifier:
    @pytest.fixture
    def verifier(self) -> VisitVerifier:
        return VisitVerifier()

    def _objective(self, target_id: str | None = "loc_tavern") -> QuestObjectiveInput:
        return QuestObjectiveInput(
            objective_id="obj_visit",
            objective_type="visit",
            target_count=1,
            target_id=target_id,
        )

    @pytest.mark.asyncio
    async def test_visit_satisfied_when_currently_located_at(self, verifier: VisitVerifier) -> None:
        repo = _repo(count_player_located_at=1)
        result = await verifier.verify(repo, "player_1", self._objective())
        assert result is True

    @pytest.mark.asyncio
    async def test_visit_satisfied_when_was_at_historically(self, verifier: VisitVerifier) -> None:
        # LOCATED_AT returns 0, WAS_AT returns 1
        repo = _repo(count_player_located_at=0, count_player_was_at=1)
        result = await verifier.verify(repo, "player_1", self._objective())
        assert result is True

    @pytest.mark.asyncio
    async def test_visit_not_satisfied_when_neither_edge(self, verifier: VisitVerifier) -> None:
        repo = _repo(count_player_located_at=0, count_player_was_at=0)
        result = await verifier.verify(repo, "player_1", self._objective())
        assert result is False

    @pytest.mark.asyncio
    async def test_visit_returns_false_when_no_target_id(self, verifier: VisitVerifier) -> None:
        repo = _repo()
        result = await verifier.verify(repo, "player_1", self._objective(target_id=None))
        assert result is False
        repo.count_player_located_at.assert_not_awaited()


# ---------------------------------------------------------------------------
# KillVerifier
# ---------------------------------------------------------------------------


class TestKillVerifier:
    @pytest.fixture
    def verifier(self) -> KillVerifier:
        return KillVerifier()

    def _objective(self, target_id: str | None = "npc_bandit") -> QuestObjectiveInput:
        return QuestObjectiveInput(
            objective_id="obj_kill",
            objective_type="kill",
            target_count=1,
            target_id=target_id,
        )

    @pytest.mark.asyncio
    async def test_kill_satisfied_when_target_inactive(self, verifier: KillVerifier) -> None:
        repo = _repo(count_target_inactive=1)
        result = await verifier.verify(repo, "player_1", self._objective())
        assert result is True

    @pytest.mark.asyncio
    async def test_kill_not_satisfied_when_target_still_active(self, verifier: KillVerifier) -> None:
        repo = _repo(count_target_inactive=0)
        result = await verifier.verify(repo, "player_1", self._objective())
        assert result is False

    @pytest.mark.asyncio
    async def test_kill_returns_false_when_no_target_id(self, verifier: KillVerifier) -> None:
        repo = _repo()
        result = await verifier.verify(repo, "player_1", self._objective(target_id=None))
        assert result is False
        repo.count_target_inactive.assert_not_awaited()


# ---------------------------------------------------------------------------
# TalkVerifier
# ---------------------------------------------------------------------------


class TestTalkVerifier:
    @pytest.fixture
    def verifier(self) -> TalkVerifier:
        return TalkVerifier()

    def _objective(self, target_id: str | None = "mira_innkeeper") -> QuestObjectiveInput:
        return QuestObjectiveInput(
            objective_id="obj_talk",
            objective_type="talk",
            target_count=1,
            target_id=target_id,
        )

    @pytest.mark.asyncio
    async def test_talk_satisfied_when_co_located(self, verifier: TalkVerifier) -> None:
        repo = _repo(count_player_co_located_with=1)
        result = await verifier.verify(repo, "player_1", self._objective())
        assert result is True

    @pytest.mark.asyncio
    async def test_talk_not_satisfied_when_not_co_located(self, verifier: TalkVerifier) -> None:
        repo = _repo(count_player_co_located_with=0)
        result = await verifier.verify(repo, "player_1", self._objective())
        assert result is False

    @pytest.mark.asyncio
    async def test_talk_returns_false_when_no_target_id(self, verifier: TalkVerifier) -> None:
        repo = _repo()
        result = await verifier.verify(repo, "player_1", self._objective(target_id=None))
        assert result is False
        repo.count_player_co_located_with.assert_not_awaited()


# ---------------------------------------------------------------------------
# verify_objectives integration
# ---------------------------------------------------------------------------


class TestVerifyObjectives:
    @pytest.mark.asyncio
    async def test_all_satisfied_returns_true(self) -> None:
        repo = _repo(count_player_located_at=1, count_target_inactive=1)
        objectives = [
            QuestObjectiveInput(objective_id="o1", objective_type="visit", target_count=1, target_id="loc_a"),
            QuestObjectiveInput(objective_id="o2", objective_type="kill", target_count=1, target_id="npc_x"),
        ]
        assert await verify_objectives(repo, "p1", objectives) is True

    @pytest.mark.asyncio
    async def test_short_circuits_on_first_failure(self) -> None:
        # visit fails (both LOCATED_AT and WAS_AT return 0); kill must NOT be queried.
        repo = _repo(count_player_located_at=0, count_player_was_at=0, count_target_inactive=1)
        objectives = [
            QuestObjectiveInput(objective_id="o1", objective_type="visit", target_count=1, target_id="loc_a"),
            QuestObjectiveInput(objective_id="o2", objective_type="kill", target_count=1, target_id="npc_x"),
        ]
        result = await verify_objectives(repo, "p1", objectives)
        assert result is False
        repo.count_target_inactive.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_objectives_returns_true(self) -> None:
        repo = _repo()
        assert await verify_objectives(repo, "p1", []) is True

    @pytest.mark.asyncio
    async def test_unknown_objective_type_returns_false(self) -> None:
        """Unknown objective type has no registered verifier — returns False."""
        repo = _repo()
        # Bypass Literal validation by constructing with model_validate
        obj = QuestObjectiveInput.model_validate({
            "objective_id": "o1",
            "objective_type": "deliver",
            "target_count": 1,
            "target_id": None,
        })
        # deliver with no target_id → False
        result = await verify_objectives(repo, "p1", [obj])
        assert result is False
