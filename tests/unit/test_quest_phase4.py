"""
test_quest_phase4.py - Unit tests for Phase 4 quest lifecycle layer.

Covers:
- QuestObjectiveInput: new objective_type and target_id fields
- QuestObjectiveBody: same schema extension in API layer
- is_trusted_reward_source: accepts any non-empty string (NPC IDs)
- DeliverVerifier: returns True when HAS_ITEM edge found, False otherwise
- verify_objectives: short-circuits on first failure; empty list returns True
- quest_handler.handle_propose_quest: returns show_quest_panel with state snapshot
- quest_handler.handle_claim_completion: verifies + progresses lifecycle
- quest_handler.handle_give_item_as_quest_claim: intercepts deliver matches; ignores mismatches

Does NOT: touch the HTTP API, Redis, or the Pygame display.
Neo4j is mocked with lightweight in-memory stubs.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.api.schemas import QuestObjectiveBody
from npc_engine.engines.quest.models import QuestObjectiveInput
from npc_engine.engines.quest.quest_engine_helpers import is_trusted_reward_source
from npc_engine.engines.interaction.models import (
    STATUS_OPEN,
    STATUS_PENDING_CONFIRM,
    UI_DIRECTIVE_NONE,
    UI_DIRECTIVE_QUEST,
    UI_DIRECTIVE_REWARD,
    InteractionProposal,
)
from npc_engine.engines.interaction.quest_verifier import DeliverVerifier, verify_objectives


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _mock_repo_with_item(has_item: bool) -> MagicMock:
    """Return a mock InteractionGraphPort whose item count is 1 or 0."""
    repo = MagicMock()
    repo.count_player_has_item = AsyncMock(return_value=1 if has_item else 0)
    return repo


def _quest_state(status: str = "accepted", objectives: list | None = None, rewards_applied: bool = False) -> dict:
    return {
        "quest_id": "test_quest",
        "player_id": "player",
        "reward_source_id": "aldric_merchant",
        "title": "Deliver the Amulet",
        "status": status,
        "objectives": objectives or [{"objective_id": "del_1", "target_count": 1, "objective_type": "deliver", "target_id": "ancient_amulet"}],
        "objective_progress": {"del_1": 0},
        "item_rewards": [],
        "currency_reward": {"amount": 50},
        "rewards_applied": rewards_applied,
    }


# ---------------------------------------------------------------------------
# QuestObjectiveInput — new fields
# ---------------------------------------------------------------------------

class TestQuestObjectiveInputFields(unittest.TestCase):
    def test_defaults(self) -> None:
        obj = QuestObjectiveInput(objective_id="o1", target_count=1)
        assert obj.objective_type == "deliver"
        assert obj.target_id is None

    def test_explicit_deliver(self) -> None:
        obj = QuestObjectiveInput(
            objective_id="o1",
            target_count=1,
            objective_type="deliver",
            target_id="ancient_amulet",
        )
        assert obj.target_id == "ancient_amulet"

    def test_other_types(self) -> None:
        for t in ("kill", "visit", "talk"):
            obj = QuestObjectiveInput(objective_id="o1", target_count=1, objective_type=t)  # type: ignore[arg-type]
            assert obj.objective_type == t

    def test_frozen(self) -> None:
        obj = QuestObjectiveInput(objective_id="o1", target_count=1)
        with pytest.raises(Exception):
            obj.objective_id = "changed"  # type: ignore[misc]


class TestQuestObjectiveBodyFields(unittest.TestCase):
    def test_defaults(self) -> None:
        body = QuestObjectiveBody(objective_id="o1", target_count=1)
        assert body.objective_type == "deliver"
        assert body.target_id is None

    def test_with_target(self) -> None:
        body = QuestObjectiveBody(objective_id="o1", target_count=1, objective_type="deliver", target_id="item_x")
        assert body.target_id == "item_x"


# ---------------------------------------------------------------------------
# is_trusted_reward_source — extended to allow NPC IDs
# ---------------------------------------------------------------------------

class TestIsTrustedRewardSource(unittest.TestCase):
    def test_system(self) -> None:
        assert is_trusted_reward_source("system") is True

    def test_npc_id(self) -> None:
        assert is_trusted_reward_source("aldric_merchant") is True

    def test_empty_string(self) -> None:
        assert is_trusted_reward_source("") is False

    def test_arbitrary_character_id(self) -> None:
        assert is_trusted_reward_source("captain_sorn") is True


# ---------------------------------------------------------------------------
# DeliverVerifier
# ---------------------------------------------------------------------------

class TestDeliverVerifier(unittest.TestCase):
    def test_player_has_item(self) -> None:
        repo = _mock_repo_with_item(has_item=True)
        obj = QuestObjectiveInput(
            objective_id="o1",
            target_count=1,
            objective_type="deliver",
            target_id="ancient_amulet",
        )
        result = _run(DeliverVerifier().verify(repo, "player", obj))
        assert result is True

    def test_player_missing_item(self) -> None:
        repo = _mock_repo_with_item(has_item=False)
        obj = QuestObjectiveInput(
            objective_id="o1",
            target_count=1,
            objective_type="deliver",
            target_id="ancient_amulet",
        )
        result = _run(DeliverVerifier().verify(repo, "player", obj))
        assert result is False

    def test_no_target_id(self) -> None:
        repo = _mock_repo_with_item(has_item=True)
        obj = QuestObjectiveInput(objective_id="o1", target_count=1, objective_type="deliver")
        result = _run(DeliverVerifier().verify(repo, "player", obj))
        assert result is False
        repo.count_player_has_item.assert_not_awaited()

    def test_count_zero_returns_false(self) -> None:
        repo = _mock_repo_with_item(has_item=False)
        obj = QuestObjectiveInput(
            objective_id="o1", target_count=1, objective_type="deliver", target_id="x"
        )
        result = _run(DeliverVerifier().verify(repo, "player", obj))
        assert result is False


# ---------------------------------------------------------------------------
# verify_objectives
# ---------------------------------------------------------------------------

class TestVerifyObjectives(unittest.TestCase):
    def test_empty_list_returns_true(self) -> None:
        repo = _mock_repo_with_item(has_item=True)
        result = _run(verify_objectives(repo, "p", []))
        assert result is True

    def test_all_satisfied(self) -> None:
        repo = _mock_repo_with_item(has_item=True)
        objs = [
            QuestObjectiveInput(objective_id="o1", target_count=1, objective_type="deliver", target_id="item_a"),
        ]
        assert _run(verify_objectives(repo, "p", objs)) is True

    def test_short_circuits_on_first_failure(self) -> None:
        repo = _mock_repo_with_item(has_item=False)
        objs = [
            QuestObjectiveInput(objective_id="o1", target_count=1, objective_type="deliver", target_id="missing_item"),
            QuestObjectiveInput(objective_id="o2", target_count=1, objective_type="deliver", target_id="other_item"),
        ]
        assert _run(verify_objectives(repo, "p", objs)) is False
        assert repo.count_player_has_item.await_count == 1

    def test_unknown_type_returns_false(self) -> None:
        repo = _mock_repo_with_item(has_item=True)
        repo.count_target_inactive = AsyncMock(return_value=0)
        obj = QuestObjectiveInput(objective_id="o1", target_count=1, objective_type="kill")
        assert _run(verify_objectives(repo, "p", [obj])) is False


# ---------------------------------------------------------------------------
# handle_propose_quest
# ---------------------------------------------------------------------------

class TestHandleProposeQuest(unittest.TestCase):
    def _mock_engine(self) -> MagicMock:
        return MagicMock()

    def _mock_repo(self, quest_state: dict | None = None) -> MagicMock:
        repo = MagicMock()
        repo.get_quest_state = AsyncMock(return_value=quest_state)
        return repo

    def test_no_quest_id_returns_no_quest_hint(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_propose_quest

        proposal = InteractionProposal(kind="propose_quest", target_id=None, payload={})
        result = _run(handle_propose_quest(
            repo=self._mock_repo(), proposal=proposal, player_id="p", npc_id="npc", engine=self._mock_engine()
        ))
        assert result.status == STATUS_OPEN
        assert result.ui_directive == UI_DIRECTIVE_NONE

    def test_quest_state_returned(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_propose_quest

        state = _quest_state()
        proposal = InteractionProposal(kind="propose_quest", target_id="test_quest", payload={})
        result = _run(handle_propose_quest(
            repo=self._mock_repo(state), proposal=proposal, player_id="player", npc_id="aldric_merchant", engine=self._mock_engine()
        ))
        assert result.status == STATUS_OPEN
        assert result.ui_directive == UI_DIRECTIVE_QUEST
        assert result.data is not None
        assert result.data["quest_id"] == "test_quest"

    def test_missing_quest_state_returns_hint(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_propose_quest

        proposal = InteractionProposal(kind="propose_quest", target_id="ghost_quest", payload={})
        result = _run(handle_propose_quest(
            repo=self._mock_repo(None), proposal=proposal, player_id="player", npc_id="npc", engine=self._mock_engine()
        ))
        assert result.narration_hint == "npc_no_active_quest"


# ---------------------------------------------------------------------------
# handle_claim_completion
# ---------------------------------------------------------------------------

class TestHandleClaimCompletion(unittest.TestCase):
    def _mock_engine(
        self,
        eval_status: str = "completed",
    ) -> MagicMock:
        engine = MagicMock()
        engine.update_objective = AsyncMock(return_value=_quest_state(status="in_progress"))
        engine.evaluate_completion = AsyncMock(return_value=_quest_state(status=eval_status))
        return engine

    def _mock_repo(self, quest_state: dict | None = None) -> MagicMock:
        repo = MagicMock()
        repo.get_quest_state = AsyncMock(return_value=quest_state)
        return repo

    def test_no_quest_id_returns_hint(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_claim_completion

        session = MagicMock()
        proposal = InteractionProposal(kind="claim_completion", target_id=None, payload={})
        result = _run(handle_claim_completion(
            repo=self._mock_repo(), proposal=proposal, player_id="p", npc_id="n", engine=self._mock_engine()
        ))
        assert result.narration_hint == "npc_no_active_quest"

    def test_objectives_not_met_returns_open(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_claim_completion

        state = _quest_state()
        proposal = InteractionProposal(kind="claim_completion", target_id="test_quest", payload={})

        with patch("npc_engine.engines.interaction.quest_handler.verify_objectives", new=AsyncMock(return_value=False)):
            session = MagicMock()
            result = _run(handle_claim_completion(
                repo=self._mock_repo(state), proposal=proposal, player_id="player", npc_id="npc", engine=self._mock_engine()
            ))
        assert result.status == STATUS_OPEN
        assert result.narration_hint == "npc_refuses_objective_not_met"

    def test_objectives_met_returns_pending_confirm(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_claim_completion

        state = _quest_state()
        proposal = InteractionProposal(kind="claim_completion", target_id="test_quest", payload={})
        engine = self._mock_engine(eval_status="completed")

        with patch("npc_engine.engines.interaction.quest_handler.verify_objectives", new=AsyncMock(return_value=True)):
            session = MagicMock()
            result = _run(handle_claim_completion(
                repo=self._mock_repo(state), proposal=proposal, player_id="player", npc_id="npc", engine=engine
            ))
        assert result.status == STATUS_PENDING_CONFIRM
        assert result.ui_directive == UI_DIRECTIVE_REWARD

    def test_quest_not_active_returns_hint(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_claim_completion

        state = _quest_state(status="offered")
        proposal = InteractionProposal(kind="claim_completion", target_id="test_quest", payload={})
        session = MagicMock()
        result = _run(handle_claim_completion(
            repo=self._mock_repo(state), proposal=proposal, player_id="player", npc_id="npc", engine=self._mock_engine()
        ))
        assert result.narration_hint == "npc_no_active_quest"


# ---------------------------------------------------------------------------
# handle_give_item_as_quest_claim
# ---------------------------------------------------------------------------

class TestHandleGiveItemAsQuestClaim(unittest.TestCase):
    def _mock_repo(self, active_quest: dict | None = None, quest_state: dict | None = None) -> MagicMock:
        repo = MagicMock()
        repo.get_active_quest_for_player = AsyncMock(return_value=active_quest)
        repo.get_quest_state = AsyncMock(return_value=quest_state)
        return repo

    def test_no_active_quest_returns_none(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_give_item_as_quest_claim

        proposal = InteractionProposal(kind="give_item", target_id="some_item", payload={})
        session = MagicMock()
        result = _run(handle_give_item_as_quest_claim(
            repo=self._mock_repo(None), proposal=proposal, player_id="player", npc_id="npc", engine=MagicMock()
        ))
        assert result is None

    def test_no_matching_deliver_objective_returns_none(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_give_item_as_quest_claim

        active = {
            "quest_id": "q1",
            "objectives": [{"objective_id": "o1", "objective_type": "deliver", "target_id": "other_item", "target_count": 1}],
            "quest_giver_id": "npc",
        }
        proposal = InteractionProposal(kind="give_item", target_id="wrong_item", payload={})
        session = MagicMock()
        result = _run(handle_give_item_as_quest_claim(
            repo=self._mock_repo(active), proposal=proposal, player_id="player", npc_id="npc", engine=MagicMock()
        ))
        assert result is None

    def test_matching_item_triggers_claim(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_give_item_as_quest_claim

        active = {
            "quest_id": "test_quest",
            "objectives": [{"objective_id": "del_1", "objective_type": "deliver", "target_id": "ancient_amulet", "target_count": 1}],
            "quest_giver_id": "aldric_merchant",
        }
        quest_state = _quest_state()
        proposal = InteractionProposal(kind="give_item", target_id="ancient_amulet", payload={})
        engine = MagicMock()
        engine.update_objective = AsyncMock(return_value=quest_state)
        engine.evaluate_completion = AsyncMock(return_value=_quest_state(status="completed"))

        with patch("npc_engine.engines.interaction.quest_handler.verify_objectives", new=AsyncMock(return_value=True)):
            session = MagicMock()
            result = _run(handle_give_item_as_quest_claim(
                repo=self._mock_repo(active, quest_state), proposal=proposal, player_id="player", npc_id="aldric_merchant", engine=engine
            ))
        assert result is not None
        assert result.status == STATUS_PENDING_CONFIRM

    def test_wrong_npc_returns_none(self) -> None:
        from npc_engine.engines.interaction.quest_handler import handle_give_item_as_quest_claim

        active = {
            "quest_id": "test_quest",
            "objectives": [{"objective_id": "del_1", "objective_type": "deliver", "target_id": "ancient_amulet", "target_count": 1}],
            "quest_giver_id": "original_giver",
        }
        proposal = InteractionProposal(kind="give_item", target_id="ancient_amulet", payload={})
        session = MagicMock()
        result = _run(handle_give_item_as_quest_claim(
            repo=self._mock_repo(active), proposal=proposal, player_id="player", npc_id="different_npc", engine=MagicMock()
        ))
        assert result is None
