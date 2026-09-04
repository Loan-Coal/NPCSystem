"""
Module: test_generation_world_guard
Layer: test (unit)
Purpose: RED anchor for ISSUE-284 — the generate verb had no requires_world guard, so
         a case whose world was never seeded generated a record against a nonexistent
         NPC instead of skipping. Pins that collect_yaml_case_records now skips (no
         HTTP POST, empty record list, a log entry) exactly as runner.py's report-verb
         guard already does.
Dependencies: unittest.mock, httpx, pytest; generation_collection, preconditions (evals/,
         on pytest pythonpath)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import httpx
import pytest

from generation_collection import collect_yaml_case_records


def _make_case(requires_world: str = "tavern") -> dict:
    """Return a minimal YAML case whose seed declares a requires_world."""
    return {
        "case_id": "case_pos_evk_tw_innkeeper_ladle_brawl",
        "seed": {"npc_id": "tw_innkeeper", "player_id": "player_eval", "requires_world": requires_world},
        "input": {"player_message": "What happened at the tavern last night?"},
        "expected": [{"kind": "tone_judge", "description": "Should be in character"}],
    }


def _mock_client_with_missing_npc(npc_id: str) -> MagicMock:
    """Return a mock client whose GET 404s only for npc_id's Character node.

    Every other GET (e.g. ensure_player_node's own existence check) returns 200, so
    the only signal distinguishing "world not seeded" is the NPC's own node lookup —
    matching what the real graph would report.
    """
    client: MagicMock = MagicMock(spec=httpx.Client)

    def _get(url: str, *args: object, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 404 if url.endswith(f"/{npc_id}") else 200
        return resp

    client.get.side_effect = _get
    return client


def test_unseeded_world_case_skips_instead_of_generating(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A case whose required NPC is absent from the graph must SKIP, not generate.

    Confirmed failing before the fix: with no guard, collect_yaml_case_records calls
    POST /v1/dialogue unconditionally, so client.post gets called and a record is
    built from whatever the (nonexistent-NPC) engine call returns.
    """
    case = _make_case()
    client = _mock_client_with_missing_npc("tw_innkeeper")

    with caplog.at_level(logging.INFO, logger="generation_collection"):
        records = collect_yaml_case_records(case, client, "http://test", rep=0)

    assert records == [], f"expected a skip (no records), got {records}"
    client.post.assert_not_called()
    assert caplog.records, "expected a log entry recording the skip"
    combined = " ".join(r.getMessage() for r in caplog.records)
    assert "tw_innkeeper" in combined, "skip log must identify the missing NPC"


def test_seeded_world_case_still_generates(caplog: pytest.LogCaptureFixture) -> None:
    """A case whose NPC IS present must still call POST /v1/dialogue as before."""
    case = _make_case()
    client: MagicMock = MagicMock(spec=httpx.Client)
    present_resp = MagicMock()
    present_resp.status_code = 200
    client.get.return_value = present_resp
    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = {"npc_response": "It was quite a night."}
    client.post.return_value = post_resp

    records = collect_yaml_case_records(case, client, "http://test", rep=0)

    client.post.assert_called_once()
    assert len(records) == 1
