"""
Module: test_memory_consolidate_scene
Layer: demo_game (tests)
Purpose: T25.6 — ACT 4 reports why consolidation did not create a Memory node.
         An LLM failure must not print "Turn threshold not met", and the scene
         sends its own turn_threshold so the scripted run has enough turns.
Dependencies: demo_game.runners.run_scenes, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.runners.run_scenes import MemoryConsolidate


def _runner_returning(data: dict) -> MagicMock:
    """Build a MagicMock runner whose consolidate_memory returns *data*."""
    runner = MagicMock()
    runner.dry_run = False
    runner.client.consolidate_memory.return_value = data
    return runner


def _printed(runner: MagicMock) -> str:
    """Return the single print_ok line the scene emitted."""
    runner.print_ok.assert_called_once()
    return runner.print_ok.call_args.args[0]


def test_sends_scene_turn_threshold() -> None:
    """The scene forwards its turn_threshold to the client."""
    runner = _runner_returning({"memory_id": "m1", "status": "created"})

    MemoryConsolidate(name="t", npc_id="mira_innkeeper", turn_threshold=1).execute(runner)

    assert runner.client.consolidate_memory.call_args.kwargs["turn_threshold"] == 1


def test_created_reports_memory_id() -> None:
    """A created memory prints its id."""
    runner = _runner_returning({"memory_id": "m1", "status": "created"})

    MemoryConsolidate(name="t", npc_id="mira_innkeeper").execute(runner)

    assert "Memory node created -- id=m1" in _printed(runner)


@pytest.mark.parametrize(
    "status, expected, forbidden",
    [
        ("llm_failed", "LLM error", "Turn threshold not met"),
        ("threshold_not_met", "Turn threshold not met", "LLM error"),
    ],
)
def test_failure_statuses_print_distinct_reasons(status: str, expected: str, forbidden: str) -> None:
    """Each non-created status prints its own reason and never the other one."""
    runner = _runner_returning({"memory_id": None, "status": status})

    MemoryConsolidate(name="t", npc_id="mira_innkeeper").execute(runner)

    line = _printed(runner)
    assert expected in line
    assert forbidden not in line
