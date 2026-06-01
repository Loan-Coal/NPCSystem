"""
test_quest_verifier.py - Unit tests for VisitVerifier, KillVerifier, TalkVerifier.

Does NOT: execute real Neo4j writes.

Dependencies injected: mock AsyncSession returning controlled results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from npc_engine.engines.interaction.quest_verifier import (
    KillVerifier,
    TalkVerifier,
    VisitVerifier,
    verify_objectives,
)
from npc_engine.engines.quest.models import QuestObjectiveInput


# ---------------------------------------------------------------------------
# Fake Neo4j session infrastructure
# ---------------------------------------------------------------------------


@dataclass
class _FakeRecord:
    data: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]


@dataclass
class _FakeResult:
    records: list[_FakeRecord] = field(default_factory=list)
    _consumed: bool = False

    async def single(self) -> _FakeRecord | None:
        return self.records[0] if self.records else None

    async def consume(self) -> None:
        self._consumed = True


class _FakeSession:
    """Fake AsyncSession that returns pre-configured results per query."""

    def __init__(self, results: list[_FakeResult]) -> None:
        self._results = list(results)
        self._calls: list[tuple[str, dict]] = []

    async def run(self, query: str, **params: Any) -> _FakeResult:
        self._calls.append((query, params))
        if self._results:
            return self._results.pop(0)
        return _FakeResult()


def _session_returning(count: int) -> _FakeSession:
    """Return a session whose first query yields a record with cnt=count."""
    return _FakeSession([_FakeResult([_FakeRecord({"cnt": count})])])


def _session_returning_sequence(*counts: int) -> _FakeSession:
    """Return a session that yields multiple results in order."""
    results = [_FakeResult([_FakeRecord({"cnt": c})]) for c in counts]
    return _FakeSession(results)


def _empty_session() -> _FakeSession:
    return _FakeSession([_FakeResult()])


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
        session = _session_returning(1)
        result = await verifier.verify(session, "player_1", self._objective())
        assert result is True

    @pytest.mark.asyncio
    async def test_visit_satisfied_when_was_at_historically(self, verifier: VisitVerifier) -> None:
        # First query (LOCATED_AT) returns 0, second (WAS_AT) returns 1
        session = _session_returning_sequence(0, 1)
        result = await verifier.verify(session, "player_1", self._objective())
        assert result is True

    @pytest.mark.asyncio
    async def test_visit_not_satisfied_when_neither_edge(self, verifier: VisitVerifier) -> None:
        session = _session_returning_sequence(0, 0)
        result = await verifier.verify(session, "player_1", self._objective())
        assert result is False

    @pytest.mark.asyncio
    async def test_visit_returns_false_when_no_target_id(self, verifier: VisitVerifier) -> None:
        session = _empty_session()
        result = await verifier.verify(session, "player_1", self._objective(target_id=None))
        assert result is False
        assert len(session._calls) == 0


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
        session = _session_returning(1)
        result = await verifier.verify(session, "player_1", self._objective())
        assert result is True

    @pytest.mark.asyncio
    async def test_kill_not_satisfied_when_target_still_active(self, verifier: KillVerifier) -> None:
        session = _session_returning(0)
        result = await verifier.verify(session, "player_1", self._objective())
        assert result is False

    @pytest.mark.asyncio
    async def test_kill_returns_false_when_no_target_id(self, verifier: KillVerifier) -> None:
        session = _empty_session()
        result = await verifier.verify(session, "player_1", self._objective(target_id=None))
        assert result is False
        assert len(session._calls) == 0

    @pytest.mark.asyncio
    async def test_kill_returns_false_when_no_record(self, verifier: KillVerifier) -> None:
        session = _FakeSession([_FakeResult(records=[])])
        result = await verifier.verify(session, "player_1", self._objective())
        assert result is False


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
        session = _session_returning(1)
        result = await verifier.verify(session, "player_1", self._objective())
        assert result is True

    @pytest.mark.asyncio
    async def test_talk_not_satisfied_when_not_co_located(self, verifier: TalkVerifier) -> None:
        session = _session_returning(0)
        result = await verifier.verify(session, "player_1", self._objective())
        assert result is False

    @pytest.mark.asyncio
    async def test_talk_returns_false_when_no_target_id(self, verifier: TalkVerifier) -> None:
        session = _empty_session()
        result = await verifier.verify(session, "player_1", self._objective(target_id=None))
        assert result is False
        assert len(session._calls) == 0

    @pytest.mark.asyncio
    async def test_talk_returns_false_when_no_record(self, verifier: TalkVerifier) -> None:
        session = _FakeSession([_FakeResult(records=[])])
        result = await verifier.verify(session, "player_1", self._objective())
        assert result is False


# ---------------------------------------------------------------------------
# verify_objectives integration
# ---------------------------------------------------------------------------


class TestVerifyObjectives:
    @pytest.mark.asyncio
    async def test_all_satisfied_returns_true(self) -> None:
        session = _session_returning_sequence(1, 1)
        objectives = [
            QuestObjectiveInput(objective_id="o1", objective_type="visit", target_count=1, target_id="loc_a"),
            QuestObjectiveInput(objective_id="o2", objective_type="kill", target_count=1, target_id="npc_x"),
        ]
        assert await verify_objectives(session=session, player_id="p1", objectives=objectives) is True

    @pytest.mark.asyncio
    async def test_short_circuits_on_first_failure(self) -> None:
        # visit makes 2 queries (LOCATED_AT, WAS_AT); both return 0 so visit fails.
        # kill query must NOT fire (short-circuit).
        session = _session_returning_sequence(0, 0, 1)
        objectives = [
            QuestObjectiveInput(objective_id="o1", objective_type="visit", target_count=1, target_id="loc_a"),
            QuestObjectiveInput(objective_id="o2", objective_type="kill", target_count=1, target_id="npc_x"),
        ]
        result = await verify_objectives(session=session, player_id="p1", objectives=objectives)
        assert result is False
        assert len(session._calls) == 2

    @pytest.mark.asyncio
    async def test_empty_objectives_returns_true(self) -> None:
        session = _empty_session()
        assert await verify_objectives(session=session, player_id="p1", objectives=[]) is True

    @pytest.mark.asyncio
    async def test_unknown_objective_type_returns_false(self) -> None:
        """Unknown objective type has no registered verifier — returns False."""
        session = _empty_session()
        # Bypass Literal validation by constructing with model_validate
        obj = QuestObjectiveInput.model_validate({
            "objective_id": "o1",
            "objective_type": "deliver",
            "target_count": 1,
            "target_id": None,
        })
        # deliver with no target_id → False
        result = await verify_objectives(session=session, player_id="p1", objectives=[obj])
        assert result is False
