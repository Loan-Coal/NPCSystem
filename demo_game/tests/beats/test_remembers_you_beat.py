"""
Module: test_remembers_you_beat
Layer: demo_game (tests)
Purpose: Unit tests for RemembersYouBeat demo scene — cross-session memory recall.
Dependencies: demo_game.beats.remembers_you_beat, unittest.mock
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from demo_game.beats.remembers_you_beat import RemembersYouBeat, _MEMORY_MESSAGE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runner(*, dry_run: bool = False, relationship: dict | None = None) -> MagicMock:
    """Build a minimal mock DemoRunner with controllable client behaviour."""
    runner = MagicMock()
    runner.dry_run = dry_run
    runner.client.get_npc_relationship.return_value = relationship
    return runner


_FAKE_EDGE = {
    "trust": 42,
    "fear": 5,
    "affection": 30,
    "interaction_count": 3,
}

_FAKE_DIALOGUE = {"npc_response": "Ah yes, I remember you well, traveller."}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_execute_dry_run_skips_all_api_calls() -> None:
    """dry_run=True must return before any client call is made."""
    runner = _make_runner(dry_run=True)
    beat = RemembersYouBeat(name="act9_remembers_you")
    beat.execute(runner)

    runner.client.get_npc_relationship.assert_not_called()
    runner.client.post_dialogue.assert_not_called()


def test_execute_skips_on_no_edge() -> None:
    """When get_npc_relationship returns None, post_dialogue must NOT be called."""
    runner = _make_runner(relationship=None)
    beat = RemembersYouBeat(name="act9_remembers_you")
    beat.execute(runner)

    runner.client.get_npc_relationship.assert_called_once_with("mira_innkeeper", "player_demo")
    runner.client.post_dialogue.assert_not_called()


def test_execute_prints_relation_and_calls_dialogue() -> None:
    """When an edge exists, post_dialogue must be called with the correct npc_id and player_id."""
    runner = _make_runner(relationship=_FAKE_EDGE)
    runner.client.post_dialogue.return_value = _FAKE_DIALOGUE
    beat = RemembersYouBeat(name="act9_remembers_you")
    beat.execute(runner)

    runner.client.post_dialogue.assert_called_once_with(
        player_id="player_demo",
        npc_id="mira_innkeeper",
        player_message=_MEMORY_MESSAGE,
    )


def test_execute_uses_memory_message_constant() -> None:
    """post_dialogue must be called with exactly _MEMORY_MESSAGE as player_message."""
    runner = _make_runner(relationship=_FAKE_EDGE)
    runner.client.post_dialogue.return_value = _FAKE_DIALOGUE
    beat = RemembersYouBeat(name="act9_remembers_you")
    beat.execute(runner)

    _, kwargs = runner.client.post_dialogue.call_args
    assert kwargs.get("player_message") == _MEMORY_MESSAGE, (
        f"Expected player_message={_MEMORY_MESSAGE!r}, got {kwargs.get('player_message')!r}"
    )
