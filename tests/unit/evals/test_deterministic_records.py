"""
Module: test_deterministic_records
Layer: test (unit)
Purpose: Unit tests for evals/deterministic_records.py (EVAL-P6.1).
Dependencies: inspect, pytest, matchers, deterministic_records, anti_hallucination_runner
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import inspect

import matchers
import pytest
from deterministic_records import (
    build_ah_grounded_record,
    build_record,
    covered_matcher_kinds,
    score_record,
)

# ---------------------------------------------------------------------------
# Guard: every non-judge matcher in matchers.py has a recorder here.
# ---------------------------------------------------------------------------

_JUDGE_ONLY_KINDS: frozenset[str] = frozenset({"tone_judge", "affirms_judge", "commits_judge"})


def test_every_matcher_kind_has_a_recorder() -> None:
    """A new _eval_* matcher without a covered_matcher_kinds() entry fails here."""
    eval_fn_names = [
        name for name, _ in inspect.getmembers(matchers, inspect.isfunction) if name.startswith("_eval_")
    ]
    derived_kinds = {name.removeprefix("_eval_") for name in eval_fn_names} - _JUDGE_ONLY_KINDS
    missing = derived_kinds - covered_matcher_kinds()
    assert not missing, f"matchers.py defines _eval_* matchers with no recorder: {missing}"


# ---------------------------------------------------------------------------
# build_record — basic construction
# ---------------------------------------------------------------------------


def test_keyword_none_expectation_produces_a_record() -> None:
    exp = {"kind": "keyword_none", "keywords": ["dragon"]}
    response = {"npc_response": "The village is quiet today."}
    record = build_record("case_001", "npc_a", "player_1", "hello", response, "keyword_none", 0, exp)
    assert record.judge_kind is None
    assert record.matcher_kind == "keyword_none"
    assert record.record_id == "case_001:keyword_none:0"
    assert record.metadata["expectation"] == exp
    assert record.metadata["response"] == response


# ---------------------------------------------------------------------------
# Matcher equivalence: score_record(build_record(...)) == matchers.evaluate(...)
# ---------------------------------------------------------------------------

_EQUIVALENCE_FIXTURES: list[tuple[str, dict, dict]] = [
    (
        "schema",
        {"kind": "schema"},
        {
            "npc_response": "Good day, traveller.",
            "relation_deltas": {"trust": 1},
            "action": {"type": "wave"},
            "facial_expression": {"type": "neutral"},
        },
    ),
    ("min_length", {"kind": "min_length", "min": 5}, {"npc_response": "hello there, friend"}),
    ("keyword_any", {"kind": "keyword_any", "keywords": ["alpha", "beta"]}, {"npc_response": "alpha rises"}),
    ("keyword_all", {"kind": "keyword_all", "keywords": ["alpha", "beta"]}, {"npc_response": "alpha and beta"}),
    ("keyword_none", {"kind": "keyword_none", "keywords": ["dragon"]}, {"npc_response": "a quiet village"}),
    (
        "in_set",
        {"kind": "in_set", "field": "action.type", "values": ["idle", "wave"]},
        {"action": {"type": "wave"}},
    ),
    (
        "range",
        {"kind": "range", "field": "relation_deltas.trust", "min": -5, "max": 5},
        {"relation_deltas": {"trust": 2}},
    ),
    ("substring", {"kind": "substring", "substring": "hello"}, {"npc_response": "well hello there"}),
    ("regex", {"kind": "regex", "pattern": r"^hello"}, {"npc_response": "hello there"}),
    (
        "context_block_expected",
        {
            "kind": "context_block_expected",
            "expected_strings": ["reputation: 80"],
            "_runner_context": "reputation: 80 (allied)",
        },
        {},
    ),
]


@pytest.mark.parametrize("kind,exp,response", _EQUIVALENCE_FIXTURES, ids=[f[0] for f in _EQUIVALENCE_FIXTURES])
def test_matcher_equivalence(kind: str, exp: dict, response: dict) -> None:
    """The transcript path reproduces matchers.evaluate()'s verdict exactly."""
    record = build_record("case", "npc", "player", "msg", response, kind, 0, exp)
    direct = matchers.evaluate(exp, response)
    replayed = score_record(record)
    assert replayed == direct


def test_covered_matcher_kinds_includes_all_ten_yaml_kinds() -> None:
    assert covered_matcher_kinds() == {
        "schema",
        "min_length",
        "keyword_any",
        "keyword_all",
        "keyword_none",
        "in_set",
        "range",
        "substring",
        "regex",
        "context_block_expected",
    }


# ---------------------------------------------------------------------------
# Grounded anti-hallucination records
# ---------------------------------------------------------------------------


def test_grounded_ah_case_produces_a_record_not_none() -> None:
    case = {
        "id": "ah_002",
        "npc_id": "captain_sorn",
        "question": "Is the war still going on?",
        "expected_verdict": "grounded",
        "expected_fact_substrings": ["war", "soldiers"],
    }
    response = {"npc_response": "The war rages on; soldiers march north."}
    record = build_ah_grounded_record(case, response, player_id="player_demo")
    assert record is not None
    assert record.judge_kind is None
    assert record.matcher_kind == "anti_hallucination_grounded"
    assert record.player_id == "player_demo"
    passed, _ = score_record(record)
    assert passed is True


def test_grounded_ah_case_fails_when_no_substring_matches() -> None:
    case = {
        "id": "ah_003",
        "npc_id": "captain_sorn",
        "question": "Is the war still going on?",
        "expected_verdict": "grounded",
        "expected_fact_substrings": ["war", "soldiers"],
    }
    response = {"npc_response": "The garden is lovely this time of year."}
    record = build_ah_grounded_record(case, response, player_id="player_demo")
    assert record is not None
    passed, _ = score_record(record)
    assert passed is False


def test_refusal_ah_case_produces_no_grounded_record() -> None:
    case = {
        "id": "ah_001",
        "npc_id": "mira_innkeeper",
        "question": "Tell me about the dragon?",
        "expected_verdict": "refusal",
        "expected_fact_substrings": [],
    }
    response = {"npc_response": "I know nothing of any dragon."}
    assert build_ah_grounded_record(case, response, player_id="player_demo") is None


# ---------------------------------------------------------------------------
# score_record error contract
# ---------------------------------------------------------------------------


def test_score_record_requires_matcher_kind() -> None:
    from eval_records import GenerationRecord

    record = GenerationRecord(
        record_id="c:tone_judge:0",
        source="runner",
        npc_id="n",
        player_id="p",
        player_message="hi",
        npc_response="hello",
        criteria="Answer YES.",
        judge_kind="tone_judge",
        expected_polarity="pass_on_yes",
    )
    with pytest.raises(ValueError, match="matcher_kind"):
        score_record(record)
