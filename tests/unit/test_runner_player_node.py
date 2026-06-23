"""
test_runner_player_node.py — Regression test: the eval runner creates the player
node unconditionally (not only as a reputation side-effect), so non-reputation
cases no longer 422 under the strict-player policy (ISSUE-118).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# evals/ is on pytest's pythonpath via pyproject.
import runner


def _resp(status: int, body: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {"data": {}}
    return r


def test_main_ensures_player_node_for_non_reputation_case() -> None:
    """A case with no faction_id still triggers ensure_player_node before running."""
    case = {
        "case_id": "case_no_rep",
        "seed": {"npc_id": "npc_1", "player_id": "player_eval"},
        "input": {"player_message": "hello"},
        "expected": [],
    }
    with (
        patch.object(runner, "_load_cases", return_value=[case]),
        patch.object(runner, "_run_case", return_value={"case_id": "case_no_rep", "passed": True, "expectations": [], "response": None, "error": None}),
        patch.object(runner, "write_report", return_value="report.md"),
        patch.object(runner.preconditions, "ensure_player_node") as ensure,
        patch("httpx.Client") as client_cls,
    ):
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = _resp(200)
        runner.main(["--base-url", "http://x", "--api-key", "k"])

    ensure.assert_called_once()
    assert ensure.call_args.args[2] == "player_eval"
