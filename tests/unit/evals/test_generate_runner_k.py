"""
Module: test_generate_runner_k
Layer: test (unit)
Purpose: Tests for k-repeat and retrieved-context capture in generate_runner.collect_records.
Dependencies: unittest.mock, generate_runner (evals/, on pytest pythonpath).
Used by: pytest (make test / make check).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from generate_runner import collect_records


def _make_yaml_case(case_id: str = "tc001") -> dict:
    """Return a minimal YAML eval case with one tone_judge expectation."""
    return {
        "case_id": case_id,
        "seed": {"npc_id": "test_npc", "player_id": "test_player"},
        "input": {"player_message": "hello world"},
        "expected": [{"kind": "tone_judge", "description": "Should be friendly"}],
    }


def _make_mock_client(*, with_context: bool = True) -> MagicMock:
    """Return a mock httpx.Client whose POST returns a dialogue and GET returns retrieval."""
    client = MagicMock()

    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = {"npc_response": "Hello there!"}
    client.post.return_value = post_resp

    get_resp = MagicMock()
    get_resp.raise_for_status = MagicMock()
    get_resp.json.return_value = {
        "context_items": [
            {"key": "memories", "tier": "A", "priority": 1, "text": "context text"}
        ]
        if with_context
        else []
    }
    client.get.return_value = get_resp

    return client


@patch("generate_runner.preconditions.ensure_player_node")
def test_k_repeats_produce_k_records_per_case(mock_ensure: MagicMock) -> None:
    """collect_records with k=2 produces twice the records of k=1.

    Each record carries the correct repetition index, a non-negative duration_ms,
    and a non-empty retrieved_context.
    """
    case = _make_yaml_case()
    client = _make_mock_client()

    records = collect_records([case], [], client, "http://test", k=2)

    # 1 tone_judge expectation × k=2 repetitions = 2 records
    assert len(records) == 2, f"Expected 2 records, got {len(records)}"
    repetitions = sorted(r.repetition for r in records)
    assert repetitions == [0, 1], f"Expected repetitions [0, 1], got {repetitions}"
    assert all(r.duration_ms >= 0 for r in records)
    assert all(len(r.retrieved_context) > 0 for r in records), (
        "Every record must carry a non-empty retrieved_context"
    )


@patch("generate_runner.preconditions.ensure_player_node")
def test_k_equals_one_is_default(mock_ensure: MagicMock) -> None:
    """collect_records with no k argument defaults to k=1 (backward compatible)."""
    case = _make_yaml_case()
    client = _make_mock_client()

    records_default = collect_records([case], [], client, "http://test")
    records_explicit = collect_records([case], [], client, "http://test", k=1)

    assert len(records_default) == 1
    assert len(records_explicit) == 1
    assert records_default[0].repetition == 0
    assert records_explicit[0].repetition == 0
