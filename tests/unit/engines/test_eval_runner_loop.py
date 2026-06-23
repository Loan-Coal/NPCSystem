"""
test_eval_runner_loop.py — Unit tests for evals/runner.py HTTP loop and main().

Complements test_eval_runner_guards.py (pure-function guard injection) by
testing the network-touching code paths with httpx mocks:
- _run_case: no-input skip, NPC-404 skip, request error, successful response
- main(): server unreachable, no cases, guarantee_not_demonstrated, all-pass
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import runner


# ---------------------------------------------------------------------------
# _run_case helpers
# ---------------------------------------------------------------------------


def _mock_200(json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_data or {}
    return resp


def _mock_404() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 404
    return resp


def _make_client(*, npc_status: int = 200, post_resp: dict | None = None) -> MagicMock:
    client = MagicMock()
    npc_check = MagicMock()
    npc_check.status_code = npc_status
    client.get.return_value = npc_check
    resp = _mock_200(post_resp)
    client.post.return_value = resp
    return client


# ---------------------------------------------------------------------------
# _run_case: no input field → skip
# ---------------------------------------------------------------------------


def test_run_case_no_input_skips() -> None:
    """A case with no 'input' field is skipped (runner cannot drive a non-dialogue endpoint)."""
    case = {"case_id": "case_schema_only", "description": "schema-only test"}
    client = _make_client()

    result = runner._run_case(case=case, client=client, base_url="http://localhost:8000")

    assert result["passed"] is True
    assert len(result["expectations"]) == 1
    assert result["expectations"][0]["skipped"] is True
    assert "SKIP" in result["expectations"][0]["detail"]
    client.get.assert_not_called()
    client.post.assert_not_called()


# ---------------------------------------------------------------------------
# _run_case: NPC not found → skip
# ---------------------------------------------------------------------------


def test_run_case_npc_not_found_skips() -> None:
    """A case whose NPC is not in the graph is skipped with an informative detail."""
    case = {
        "case_id": "case_x",
        "input": {"player_message": "hello"},
        "seed": {"npc_id": "ghost_npc"},
    }
    client = _make_client(npc_status=404)

    result = runner._run_case(case=case, client=client, base_url="http://localhost:8000")

    assert result["passed"] is True
    assert result["expectations"][0]["skipped"] is True
    assert "ghost_npc" in result["expectations"][0]["detail"]
    client.post.assert_not_called()


# ---------------------------------------------------------------------------
# _run_case: request error → case fails
# ---------------------------------------------------------------------------


def test_run_case_post_request_error_fails() -> None:
    """A POST that raises maps to result.error != None and passed=False."""
    import httpx

    case = {
        "case_id": "case_x",
        "input": {"player_message": "hello"},
        "expected": [],
    }
    client = _make_client()
    client.post.side_effect = httpx.ConnectError("Connection refused")

    result = runner._run_case(case=case, client=client, base_url="http://localhost:8000")

    assert result["error"] is not None
    assert "Connection refused" in result["error"]
    assert result["passed"] is False


# ---------------------------------------------------------------------------
# _run_case: successful response, no expectations → passes
# ---------------------------------------------------------------------------


def test_run_case_success_no_expectations_passes() -> None:
    """A case with an empty expected list and a clean 200 response passes."""
    case = {
        "case_id": "case_003_trade",
        "input": {"player_message": "What do you sell?"},
        "expected": [],
    }
    post_data = {"npc_response": "I have many fine goods."}
    client = _make_client(post_resp=post_data)

    result = runner._run_case(case=case, client=client, base_url="http://localhost:8000")

    assert result["passed"] is True
    assert result["error"] is None


# ---------------------------------------------------------------------------
# _run_case: keyword_none expectation hit → case fails
# ---------------------------------------------------------------------------


def test_run_case_keyword_none_fails_when_keyword_present() -> None:
    """A keyword_none expectation fails when the NPC response contains a forbidden keyword."""
    case = {
        "case_id": "case_neg_x",
        "input": {"player_message": "Is peace at hand?"},
        "expected": [{"kind": "keyword_none", "keywords": ["peace has arrived"]}],
    }
    post_data = {"npc_response": "Indeed, peace has arrived at last!"}
    client = _make_client(post_resp=post_data)

    result = runner._run_case(case=case, client=client, base_url="http://localhost:8000")

    failed = [e for e in result["expectations"] if not e.get("skipped") and not e["passed"]]
    assert len(failed) >= 1
    kinds = [e["kind"] for e in failed]
    assert "keyword_none" in kinds


# ---------------------------------------------------------------------------
# main(): server unreachable → exit code 2
# ---------------------------------------------------------------------------


def test_main_server_unreachable_exits_2() -> None:
    """main() returns 2 when the server is not reachable."""
    import httpx

    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.ConnectError("refused")
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)

    with (
        patch("runner.httpx.Client", return_value=mock_client),
        patch("runner._load_cases", return_value=[{"case_id": "c1"}]),
    ):
        code = runner.main(["--base-url", "http://localhost:8000", "--cases", "evals/cases"])

    assert code == 2


# ---------------------------------------------------------------------------
# main(): no cases found → exit code 2
# ---------------------------------------------------------------------------


def test_main_no_cases_exits_2(tmp_path: Path) -> None:
    """main() returns 2 when the cases directory is empty."""
    empty_dir = tmp_path / "cases"
    empty_dir.mkdir()

    code = runner.main(["--cases", str(empty_dir)])

    assert code == 2


# ---------------------------------------------------------------------------
# main(): guarantee_demonstrated=False → exit code 1
# ---------------------------------------------------------------------------


def test_main_guarantee_not_demonstrated_exits_1(tmp_path: Path) -> None:
    """main() returns 1 when the anti-hallucination guarantee was not demonstrated."""
    mock_summary = SimpleNamespace(
        guarantee_demonstrated=False,
        guard_turns=0,
        hallucination_failures=0,
    )
    mock_client = MagicMock()
    mock_health = _mock_200()
    mock_client.get.return_value = mock_health
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    with (
        patch("runner.httpx.Client", return_value=mock_client),
        patch("runner._load_cases", return_value=[{"case_id": "c1"}]),
        patch("runner._setup_reputation"),
        patch("runner._run_case", return_value={
            "case_id": "c1", "passed": True, "expectations": [], "response": None, "error": None,
        }),
        patch("runner.write_report", return_value=reports_dir / "report.json"),
        patch("runner.summarize", return_value=mock_summary),
        patch("runner.format_summary_lines", return_value=[]),
    ):
        code = runner.main(["--base-url", "http://localhost:8000", "--cases", "evals/cases",
                            "--reports", str(reports_dir)])

    assert code == 1


# ---------------------------------------------------------------------------
# main(): all pass + guarantee demonstrated → exit code 0
# ---------------------------------------------------------------------------


def test_main_all_pass_exits_0(tmp_path: Path) -> None:
    """main() returns 0 when every case passes and the guarantee is demonstrated."""
    mock_summary = SimpleNamespace(
        guarantee_demonstrated=True,
        guard_turns=1,
        hallucination_failures=0,
    )
    mock_client = MagicMock()
    mock_health = _mock_200()
    mock_client.get.return_value = mock_health
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    with (
        patch("runner.httpx.Client", return_value=mock_client),
        patch("runner._load_cases", return_value=[{"case_id": "c1"}]),
        patch("runner._setup_reputation"),
        patch("runner._run_case", return_value={
            "case_id": "c1", "passed": True, "expectations": [], "response": None, "error": None,
        }),
        patch("runner.write_report", return_value=reports_dir / "report.json"),
        patch("runner.summarize", return_value=mock_summary),
        patch("runner.format_summary_lines", return_value=[]),
    ):
        code = runner.main(["--base-url", "http://localhost:8000", "--cases", "evals/cases",
                            "--reports", str(reports_dir)])

    assert code == 0
