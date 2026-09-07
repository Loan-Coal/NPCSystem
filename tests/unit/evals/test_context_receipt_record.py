"""
Module: test_context_receipt_record
Layer: test (unit)
Purpose: The transcript-side context receipt (item C3) — the record model, its parser,
         and generate_runner storing what the engine actually assembled instead of the
         approximation from a second debug-endpoint call.
Dependencies: unittest.mock, pytest; context_receipt_record, transcript_models,
              generate_runner (evals/, on pytest pythonpath).
Used by: pytest (make test / make check).

Why this is a correctness test, not a plumbing one. `retrieved_context` was captured by a
SECOND call to /v1/admin/debug/retrieval with session_turns=[], so it described a different
assembly than the one that produced the reply. Retrieval precision computed over it is
precision over what the retriever RANKED, which is not the same number as precision over
what REACHED THE MODEL.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from context_receipt_record import ContextReceiptRecord, DroppedItemRecord, parse_context_receipt
from transcript_models import GenerationRecord

_RECEIPT_PAYLOAD = {
    "retrieval_profile": "aggressive",
    "item_keys": ["character:npc_1", "world_state"],
    "dropped_keys": ["rag:r1"],
    "dropped": [{"key": "rag:r1", "tier": "tierC", "reason": "prompt_budget"}],
    "tier_spend": [
        {"tier": "tier0", "items": 1, "tokens": 12},
        {"tier": "tierA", "items": 1, "tokens": 30},
        {"tier": "tierB", "items": 0, "tokens": 0},
        {"tier": "tierC", "items": 0, "tokens": 0},
    ],
    "total_tokens": 42,
    "prompt_token_budget": 512,
    "budget_trimmed": True,
}


# ---------------------------------------------------------------------------
# The record model and its parser
# ---------------------------------------------------------------------------


def test_parses_a_full_engine_receipt() -> None:
    receipt = parse_context_receipt(_RECEIPT_PAYLOAD)

    assert isinstance(receipt, ContextReceiptRecord)
    assert receipt.retrieval_profile == "aggressive"
    assert receipt.item_keys == ("character:npc_1", "world_state")
    assert receipt.dropped_keys == ("rag:r1",)
    assert receipt.budget_trimmed is True
    assert receipt.total_tokens == 42
    assert tuple(row.tier for row in receipt.tier_spend) == ("tier0", "tierA", "tierB", "tierC")


def test_parses_dropped_items_with_their_attributed_reason() -> None:
    """DEC-271: `dropped` carries per-item drop reason, additive to `dropped_keys`."""
    receipt = parse_context_receipt(_RECEIPT_PAYLOAD)

    assert receipt is not None
    assert receipt.dropped == (DroppedItemRecord(key="rag:r1", tier="tierC", reason="prompt_budget"),)


def test_a_payload_with_only_dropped_keys_still_parses_dropped_as_empty() -> None:
    """A payload predating this field (only the flat dropped_keys list) must still parse."""
    payload = dict(_RECEIPT_PAYLOAD)
    del payload["dropped"]

    receipt = parse_context_receipt(payload)

    assert receipt is not None
    assert receipt.dropped == ()
    assert receipt.dropped_keys == ("rag:r1",)


def test_an_absent_receipt_parses_to_none_rather_than_an_empty_receipt() -> None:
    """A turn that reported no receipt must not become a record claiming an empty context."""
    assert parse_context_receipt(None) is None
    assert parse_context_receipt({}) is None


def test_a_malformed_receipt_parses_to_none_rather_than_raising() -> None:
    """One bad payload must not abort an ~85-minute generation pass."""
    assert parse_context_receipt({"retrieval_profile": 7, "item_keys": "not-a-list"}) is None
    assert parse_context_receipt("nonsense") is None


def test_the_record_is_frozen() -> None:
    receipt = parse_context_receipt(_RECEIPT_PAYLOAD)
    assert receipt is not None
    with pytest.raises(ValidationError):
        receipt.retrieval_profile = "tampered"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GenerationRecord carries it, and old corpora still load
# ---------------------------------------------------------------------------


def _bare_record_payload() -> dict:
    return {
        "record_id": "tc001:tone_judge:0",
        "source": "runner",
        "npc_id": "npc_1",
        "player_id": "p1",
        "player_message": "hi",
        "npc_response": "hello",
        "criteria": "friendly",
        "judge_kind": "tone_judge",
        "expected_polarity": "pass_on_yes",
    }


def test_generation_record_defaults_the_receipt_so_committed_corpora_still_load() -> None:
    """evals/generations/k3_73e6c36/ predates this field and must keep deserialising."""
    record = GenerationRecord(**_bare_record_payload())

    assert record.context_receipt is None


def test_generation_record_round_trips_a_receipt_through_jsonl() -> None:
    record = GenerationRecord(
        **_bare_record_payload(), context_receipt=parse_context_receipt(_RECEIPT_PAYLOAD),
    )

    restored = GenerationRecord(**json.loads(record.model_dump_json()))

    assert restored.context_receipt is not None
    assert restored.context_receipt.item_keys == ("character:npc_1", "world_state")


# ---------------------------------------------------------------------------
# generate_runner stores the receipt the engine returned
# ---------------------------------------------------------------------------


def _yaml_case() -> dict:
    return {
        "case_id": "tc001",
        "seed": {"npc_id": "test_npc", "player_id": "test_player"},
        "input": {"player_message": "hello world"},
        "expected": [{"kind": "tone_judge", "description": "Should be friendly"}],
    }


def _mock_client() -> MagicMock:
    client = MagicMock()
    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = {
        "npc_response": "Hello there!", "context_receipt": _RECEIPT_PAYLOAD,
    }
    client.post.return_value = post_resp
    get_resp = MagicMock()
    get_resp.raise_for_status = MagicMock()
    get_resp.json.return_value = {"context_items": [
        {"key": "memories", "tier": "A", "priority": 1, "text": "context text"},
    ]}
    client.get.return_value = get_resp
    return client


@patch("generation_collection.preconditions.ensure_player_node")
def test_generate_runner_asks_the_engine_for_a_receipt(mock_ensure: MagicMock) -> None:
    """Without the opt-in flag the engine returns nothing and C3 is silently a no-op."""
    from generation_collection import collect_records

    client = _mock_client()
    collect_records([_yaml_case()], [], client, "http://x", k=1)

    body = client.post.call_args.kwargs["json"]
    assert body["include_context_receipt"] is True


@patch("generation_collection.preconditions.ensure_player_node")
def test_generate_runner_stores_the_receipt_on_every_record(mock_ensure: MagicMock) -> None:
    from generation_collection import collect_records

    records = collect_records([_yaml_case()], [], _mock_client(), "http://x", k=2)

    assert records, "the fixture case must produce at least one record"
    assert all(r.context_receipt is not None for r in records)
    assert all(r.context_receipt.retrieval_profile == "aggressive" for r in records)  # type: ignore[union-attr]


@patch("generation_collection.preconditions.ensure_player_node")
def test_the_deprecated_approximation_is_still_captured_for_one_release(
    mock_ensure: MagicMock,
) -> None:
    """retrieved_context stays until consumers move over; removing both at once would
    silently zero retrieval_join's recall@k."""
    from generation_collection import collect_records

    records = collect_records([_yaml_case()], [], _mock_client(), "http://x", k=1)

    assert all(len(r.retrieved_context) > 0 for r in records)


def test_the_approximation_is_marked_deprecated_where_a_reader_will_see_it() -> None:
    """A caveat only in a commit message is a caveat nobody reads."""
    source = Path("evals/retrieved_item.py").read_text(encoding="utf-8")

    assert "DEPRECATED" in source
    assert "context_receipt" in source
