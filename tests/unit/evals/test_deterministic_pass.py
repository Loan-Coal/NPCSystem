"""
Module: test_deterministic_pass
Layer: test (unit)
Purpose: Tests for evals/deterministic_pass.py — wires entity and knowledge scorers
         over a GenerationRecord sequence with no LLM calls.
Dependencies: pytest, deterministic_pass, entity_scorer,
              graph_vocabulary, eval_records
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from deterministic_pass import DeterministicPassResult, RecordScore, score_transcript
from entity_scorer import AliasTable
from eval_records import GenerationRecord
from graph_vocabulary import GraphVocabulary


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------


def _make_record(record_id: str, npc_id: str, npc_response: str) -> GenerationRecord:
    """Build a minimal GenerationRecord for testing."""
    return GenerationRecord(
        record_id=record_id,
        source="runner",
        npc_id=npc_id,
        player_id="player_eval",
        player_message="tell me about the war",
        npc_response=npc_response,
        criteria="",
        judge_kind=None,
        expected_polarity="pass_on_yes",
    )


_VOCAB = GraphVocabulary(
    ids=frozenset({"mira_innkeeper", "captain_sorn", "northern_war_begins"})
)
_ALIASES = AliasTable(
    aliases={
        "mira_innkeeper": "mira_innkeeper",
        "captain_sorn": "captain_sorn",
    }
)
_EVENT_VOCAB: frozenset[str] = frozenset({"northern_war_begins"})

# captain_sorn has a direct KNOWS_ABOUT edge; old_henryk does not (demo world).
_NPC_KNOWN: dict[str, frozenset[str]] = {
    "captain_sorn": frozenset({"northern_war_begins"}),
}

# Two records: sorn is permitted to reference the event; henryk is not.
_RECORDS = [
    _make_record(
        "rec-sorn-1",
        "captain_sorn",
        "The northern_war_begins changed the balance of power — captain_sorn confirmed it.",
    ),
    _make_record(
        "rec-henryk-1",
        "old_henryk",
        "I heard northern_war_begins has caused great suffering.",
    ),
]


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_scores_every_record() -> None:
    """score_transcript scores all records.

    "No LLM" is structural, not asserted here: deterministic_pass imports no module that
    reaches matchers._run_binary_judge, so a mock on it could never be called (T11.1c review).
    """
    result = score_transcript(
        _RECORDS,
        vocabulary=_VOCAB,
        aliases=_ALIASES,
        event_vocabulary=_EVENT_VOCAB,
        npc_known_events=_NPC_KNOWN,
    )
    assert result.record_count == 2
    assert len(result.record_scores) == 2


# ---------------------------------------------------------------------------
# Per-record knowledge correctness
# ---------------------------------------------------------------------------


def test_captain_sorn_has_zero_knowledge_violations() -> None:
    """northern_war_begins is permitted for sorn via npc_known_events."""
    result = score_transcript(
        [_RECORDS[0]],
        vocabulary=_VOCAB,
        aliases=_ALIASES,
        event_vocabulary=_EVENT_VOCAB,
        npc_known_events=_NPC_KNOWN,
    )
    assert result.record_scores[0].knowledge.violations == 0


def test_old_henryk_has_one_knowledge_violation() -> None:
    """northern_war_begins is a violation for henryk — not in npc_known_events."""
    result = score_transcript(
        [_RECORDS[1]],
        vocabulary=_VOCAB,
        aliases=_ALIASES,
        event_vocabulary=_EVENT_VOCAB,
        npc_known_events=_NPC_KNOWN,
    )
    assert result.record_scores[0].knowledge.violations == 1


# ---------------------------------------------------------------------------
# Aggregate rate arithmetic
# ---------------------------------------------------------------------------


def test_aggregate_entity_rate_zero_when_all_known() -> None:
    """All alias matches resolve to known IDs → aggregate entity_rate 0.0."""
    result = score_transcript(
        _RECORDS,
        vocabulary=_VOCAB,
        aliases=_ALIASES,
        event_vocabulary=_EVENT_VOCAB,
        npc_known_events=_NPC_KNOWN,
    )
    assert result.entity_rate == 0.0


def test_aggregate_knowledge_rate_nonzero_with_violation() -> None:
    """Henryk's violation contributes to aggregate knowledge_rate > 0.0."""
    result = score_transcript(
        _RECORDS,
        vocabulary=_VOCAB,
        aliases=_ALIASES,
        event_vocabulary=_EVENT_VOCAB,
        npc_known_events=_NPC_KNOWN,
    )
    # 2 event references total (1 sorn, 1 henryk), 1 violation → rate > 0
    assert result.knowledge_rate > 0.0


# ---------------------------------------------------------------------------
# Empty transcript edge case
# ---------------------------------------------------------------------------


def test_empty_transcript_returns_zero_rates() -> None:
    """Empty record list → record_count 0, entity_rate 0.0, knowledge_rate 0.0."""
    result = score_transcript(
        [],
        vocabulary=_VOCAB,
        aliases=_ALIASES,
        event_vocabulary=_EVENT_VOCAB,
        npc_known_events={},
    )
    assert result.record_count == 0
    assert result.entity_rate == 0.0
    assert result.knowledge_rate == 0.0


# ---------------------------------------------------------------------------
# Result model immutability
# ---------------------------------------------------------------------------


def test_deterministic_pass_result_is_frozen() -> None:
    """DeterministicPassResult must be immutable after construction."""
    result = score_transcript(
        [],
        vocabulary=_VOCAB,
        aliases=_ALIASES,
        event_vocabulary=_EVENT_VOCAB,
        npc_known_events={},
    )
    with pytest.raises(ValidationError, match="Instance is frozen"):
        result.record_count = 99  # type: ignore[misc]
