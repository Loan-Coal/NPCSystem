"""
Module: deterministic_records
Layer: evals (eval harness — not part of src/)
Purpose: Build and replay judge_kind=None GenerationRecords for non-judge expectation
         kinds (schema, min_length, keyword_*, in_set, range, substring, regex,
         context_block_expected) plus grounded anti-hallucination cases, so the
         transcript path scores the full case battery instead of a strict subset
         of matchers.py (EVAL-P6.1).
Dependencies: typing (get_args), matchers, eval_records, anti_hallucination_runner
         (reuses the private _is_grounded predicate — stable sibling helper, same
         pattern generate_runner already uses for _load_fixture/_PLAYER_ID)
Used by: generate_runner (record construction), deterministic_pass/report consumers
         that want to replay a deterministic verdict without re-calling the engine
Does NOT: call the LLM judge, call /v1/dialogue, modify graph state
"""

from __future__ import annotations

from typing import Any, get_args

import matchers
from anti_hallucination_runner import _is_grounded
from eval_records import DeterministicMatcherKind, GenerationRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The grounded AH check isn't a matchers.py kind (it has its own predicate,
# _is_grounded), so it's excluded from the set matchers.evaluate() dispatches on.
_GROUNDED_MATCHER_KIND: str = "anti_hallucination_grounded"

_YAML_MATCHER_KINDS: frozenset[str] = frozenset(get_args(DeterministicMatcherKind)) - {
    _GROUNDED_MATCHER_KIND
}

_DEFAULT_POLARITY: str = "pass_on_yes"  # unused filler for judge_kind=None records


# ---------------------------------------------------------------------------
# Coverage introspection (backs the "no matcher left unrecorded" guard test)
# ---------------------------------------------------------------------------


def covered_matcher_kinds() -> frozenset[str]:
    """Return the non-judge matcher kinds this module can record and replay.

    Used by tests/unit/evals/test_deterministic_records.py to assert every
    _eval_* function in matchers.py (other than the two LLM judges) has a
    corresponding entry here — a new matcher added without extending
    eval_records.DeterministicMatcherKind fails that test immediately.

    Returns:
        Frozen set of matcher kind strings (excludes the AH-grounded pseudo-kind).
    """
    return _YAML_MATCHER_KINDS


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------


def build_record(
    case_id: str,
    npc_id: str,
    player_id: str,
    player_message: str,
    response: dict[str, Any],
    kind: str,
    index: int,
    exp: dict[str, Any],
) -> GenerationRecord:
    """Build one deterministic (judge_kind=None) GenerationRecord for an expectation.

    Stores the raw expectation and the full API response verbatim in metadata so
    score_record can reproduce matchers.evaluate()'s verdict without re-calling
    the engine — including matchers that check fields other than npc_response
    (in_set/range on facial_expression.type, action.type, relation_deltas.*).

    Args:
        case_id: The owning YAML case's case_id.
        npc_id: Character that produced the response.
        player_id: Player interacting with the NPC.
        player_message: The player's dialogue turn.
        response: Full parsed /v1/dialogue response body.
        kind: The expectation's matcher kind (must be in covered_matcher_kinds()).
        index: Position of this expectation within the case's expected list —
            shared numbering with judge records so record_ids never collide.
        exp: The raw expectation dict, stored verbatim for replay.
    Returns:
        A frozen GenerationRecord with judge_kind=None, matcher_kind=kind.
    """
    return GenerationRecord(
        record_id=f"{case_id}:{kind}:{index}",
        source="runner",
        npc_id=npc_id,
        player_id=player_id,
        player_message=player_message,
        npc_response=response.get("npc_response", "") or "",
        criteria="",
        judge_kind=None,
        matcher_kind=kind,
        expected_polarity=_DEFAULT_POLARITY,
        metadata={"expectation": exp, "response": response},
    )


def build_ah_grounded_record(
    case: dict[str, Any], response: dict[str, Any], player_id: str
) -> GenerationRecord | None:
    """Build a deterministic grounded-check record for an AH fixture case.

    Mirrors the inverse of generate_runner._build_ah_record: returns None for
    refusal cases (those get a refusal_judge record instead), and a record for
    grounded cases — closing the EVAL-P6.1 gap where grounded AH cases were
    silently dropped from the transcript.

    Args:
        case: Anti-hallucination fixture case dict.
        response: Full parsed /v1/dialogue response body.
        player_id: The player id used for the dialogue call (AH cases don't carry
            their own — the caller passes the fixture-wide player, mirroring
            generate_runner._build_ah_record's use of _AH_PLAYER_ID).
    Returns:
        GenerationRecord or None (refusal cases).
    """
    if case.get("expected_verdict") != "grounded":
        return None
    substrings = case.get("expected_fact_substrings", [])
    return GenerationRecord(
        record_id=f"{case['id']}:{_GROUNDED_MATCHER_KIND}:0",
        source="anti_hallucination",
        npc_id=case["npc_id"],
        player_id=player_id,
        player_message=case.get("question", ""),
        npc_response=response.get("npc_response", "") or "",
        criteria="",
        judge_kind=None,
        matcher_kind=_GROUNDED_MATCHER_KIND,
        expected_polarity=_DEFAULT_POLARITY,
        metadata={"expected_fact_substrings": substrings, "response": response},
    )


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


def score_record(record: GenerationRecord) -> tuple[bool, str]:
    """Replay a deterministic record's matcher verdict without calling the engine.

    Args:
        record: A GenerationRecord with judge_kind=None and matcher_kind set.
    Returns:
        (passed, detail) — identical to what matchers.evaluate() (or, for the
        grounded AH kind, anti_hallucination_runner._is_grounded) returned live.
    Raises:
        ValueError: If record.matcher_kind is None (not a deterministic record),
            or if the underlying evaluator returns a JudgeResult (a deterministic
            record must never carry a judge kind).
        EvalConfigError: Propagated from matchers.evaluate() for mis-configured
            expectations (e.g. keyword_any with fewer than 2 keywords) — the same
            contract as the live path.
    """
    if record.matcher_kind is None:
        raise ValueError(f"score_record requires matcher_kind to be set: {record.record_id!r}")

    if record.matcher_kind == _GROUNDED_MATCHER_KIND:
        substrings: list[str] = record.metadata.get("expected_fact_substrings", [])
        text: str = record.metadata.get("response", {}).get("npc_response", record.npc_response)
        passed = _is_grounded(text, substrings)
        verdict = "matched" if passed else "not matched"
        return passed, f"anti_hallucination_grounded: substrings={substrings!r} {verdict}"

    expectation: dict[str, Any] = record.metadata.get("expectation", {})
    response: dict[str, Any] = record.metadata.get("response", {"npc_response": record.npc_response})
    result = matchers.evaluate(expectation, response)
    if isinstance(result, matchers.JudgeResult):
        raise ValueError(
            f"deterministic record {record.record_id!r} (matcher_kind={record.matcher_kind!r}) "
            f"replayed to a JudgeResult — this matcher kind must not be recorded here"
        )
    return (bool(result[0]), str(result[1]))
