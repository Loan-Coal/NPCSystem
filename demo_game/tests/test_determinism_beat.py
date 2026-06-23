"""
Module: test_determinism_beat
Layer: demo_game (tests)
Purpose: Unit tests for DeterminismBeat scene — verifies HTTP calls, seed table
         printing, seeds_match assertion, and dry_run short-circuit.
Dependencies: demo_game.beats.determinism_beat, unittest.mock (no network, no engine)
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from demo_game.client import EngineClient
from demo_game.beats.determinism_beat import DeterminismBeat, _GOSSIP_TICK_PATH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEED_VALUE = 982341209
_PAIR_KEY = "captain_sorn→mira_innkeeper"

_TICK_RESPONSE = {
    "status": "ok",
    "data": {
        "tick_id": 42,
        "pairs": 1,
        "propagated": 1,
        "seeds_used": {_PAIR_KEY: _SEED_VALUE},
    },
}


def _make_runner(
    response_body: dict | None = None,
    dry_run: bool = False,
) -> MagicMock:
    """Build a minimal DemoRunner mock with an injected EngineClient mock."""
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = response_body or _TICK_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_http.post.return_value = mock_resp

    client = EngineClient("http://test", "secret", _http_client=mock_http)

    runner = MagicMock()
    runner.dry_run = dry_run
    runner.client = client
    runner.client._graph_timeout = 15.0
    return runner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dry_run_returns_without_http_call() -> None:
    runner = _make_runner(dry_run=True)
    beat = DeterminismBeat(name="test_dry_run")
    beat.execute(runner)
    runner.client._client.post.assert_not_called()


def test_calls_gossip_tick_twice() -> None:
    runner = _make_runner()
    beat = DeterminismBeat(name="test_calls_twice")
    beat.execute(runner)
    assert runner.client._client.post.call_count == 2


def test_posts_correct_payload() -> None:
    runner = _make_runner()
    beat = DeterminismBeat(name="test_payload", tick_override=42)
    beat.execute(runner)

    expected_json = {
        "tick_override": 42,
        "npc_ids": ["captain_sorn", "mira_innkeeper"],
        "max_pairs": 1,
    }
    for actual_call in runner.client._client.post.call_args_list:
        _, kwargs = actual_call
        assert kwargs["json"] == expected_json


def test_seeds_match_prints_ok() -> None:
    runner = _make_runner()
    beat = DeterminismBeat(name="test_seeds_match")
    beat.execute(runner)
    runner.print_ok.assert_called_with("seeds_match=True")


def test_seeds_mismatch_raises() -> None:
    mock_http = MagicMock()
    resp1 = MagicMock()
    resp1.raise_for_status = MagicMock()
    resp1.json.return_value = {
        "data": {"seeds_used": {_PAIR_KEY: 111}}
    }
    resp2 = MagicMock()
    resp2.raise_for_status = MagicMock()
    resp2.json.return_value = {
        "data": {"seeds_used": {_PAIR_KEY: 999}}
    }
    mock_http.post.side_effect = [resp1, resp2]

    client = EngineClient("http://test", "secret", _http_client=mock_http)
    runner = MagicMock()
    runner.dry_run = False
    runner.client = client
    runner.client._graph_timeout = 15.0

    beat = DeterminismBeat(name="test_mismatch")
    with pytest.raises(AssertionError, match="Determinism check FAILED"):
        beat.execute(runner)


def test_seed_table_printed_for_each_pair() -> None:
    runner = _make_runner()
    beat = DeterminismBeat(name="test_table")
    beat.execute(runner)
    # print_step should be called at least once with the pair key in the output
    step_calls = [str(c) for c in runner.print_step.call_args_list]
    assert any(_PAIR_KEY in c for c in step_calls)
