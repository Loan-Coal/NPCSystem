"""
Module: generation_records
Layer: evals (eval harness — not part of src/)
Purpose: Build GenerationRecords for one case's expectations — judge records
         (tone_judge/affirms_judge) and, via deterministic_records, every other
         covered matcher kind (EVAL-P6.1). Split out of generate_runner.py to keep
         that module under the 300-line cap: generate_runner owns the HTTP collection
         loop and CLI; this module owns "given a case + response, build its records".
Dependencies: typing; matchers (_AFFIRMATION_CRITERIA_TMPL, _REFUSAL_CRITERIA),
         eval_records (GenerationRecord), deterministic_records, runner
         (_expected_with_guards)
Used by: generate_runner (collect_records' per-case helpers)
Does NOT: call /v1/dialogue, call the LLM judge, modify graph state
"""

from __future__ import annotations

from typing import Any

import deterministic_records
from eval_records import GenerationRecord
from matchers import _AFFIRMATION_CRITERIA_TMPL, _REFUSAL_CRITERIA
from runner import _expected_with_guards

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LLM_JUDGE_KINDS: frozenset[str] = frozenset({"tone_judge", "affirms_judge"})


# ---------------------------------------------------------------------------
# Criteria derivation helpers
# ---------------------------------------------------------------------------


def _criteria_for_tone(exp: dict) -> str:
    """Extract the judge criteria string from a tone_judge expectation."""
    return str(exp.get("judge_prompt") or exp.get("description", ""))


def _criteria_for_affirms(exp: dict) -> str:
    """Derive criteria for an affirms_judge expectation, mirroring matchers._eval_affirms_judge."""
    claim = exp.get("claim")
    if claim:
        return str(_AFFIRMATION_CRITERIA_TMPL.format(claim=str(claim).strip()))
    return str(exp.get("description", ""))


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------


def build_judge_record(
    case_id: str,
    npc_id: str,
    player_id: str,
    player_message: str,
    npc_response: str,
    kind: str,
    index: int,
    exp: dict,
) -> GenerationRecord:
    """Build one LLM-judge GenerationRecord (tone_judge or affirms_judge)."""
    if kind == "tone_judge":
        criteria = _criteria_for_tone(exp)
        polarity = "pass_on_yes"
    else:  # affirms_judge
        criteria = _criteria_for_affirms(exp)
        polarity = "pass_on_no"

    return GenerationRecord(
        record_id=f"{case_id}:{kind}:{index}",
        source="runner",
        npc_id=npc_id,
        player_id=player_id,
        player_message=player_message,
        npc_response=npc_response,
        criteria=criteria,
        judge_kind=kind,
        expected_polarity=polarity,
    )


def build_yaml_case_records(
    case: dict,
    response: dict[str, Any],
    *,
    default_player_id: str,
) -> list[GenerationRecord]:
    """Build one GenerationRecord per expectation in a YAML case.

    LLM-judge expectations (tone_judge, affirms_judge) get a judge record; every
    other covered matcher kind (schema, min_length, keyword_*, in_set, range,
    substring, regex, context_block_expected) gets a deterministic record via
    deterministic_records.build_record (EVAL-P6.1). Unrecognized kinds are not
    recorded — matchers.evaluate() itself reports "unknown expectation kind" for
    those in the live runner path.

    Args:
        case: YAML eval case dict (case_id, seed, input, expected).
        response: Full parsed /v1/dialogue response body.
        default_player_id: Player id to use when the case's seed omits one.
    Returns:
        List of GenerationRecords, one per judge or deterministic expectation.
    """
    records: list[GenerationRecord] = []
    case_id: str = case.get("case_id", "")
    npc_id: str = case.get("seed", {}).get("npc_id", "")
    player_id: str = case.get("seed", {}).get("player_id", default_player_id)
    player_message: str = case.get("input", {}).get("player_message", "")
    npc_response: str = response.get("npc_response", "") or ""

    for i, exp in enumerate(_expected_with_guards(case)):
        kind = exp.get("kind", "")
        if kind in LLM_JUDGE_KINDS:
            records.append(
                build_judge_record(case_id, npc_id, player_id, player_message, npc_response, kind, i, exp)
            )
        elif kind in deterministic_records.covered_matcher_kinds():
            records.append(
                deterministic_records.build_record(case_id, npc_id, player_id, player_message, response, kind, i, exp)
            )
    return records


def build_ah_refusal_record(case: dict, npc_response: str, *, player_id: str) -> GenerationRecord | None:
    """Build a refusal_judge GenerationRecord for an AH fixture case.

    Returns None for grounded cases (expected_verdict != 'refusal') — those get a
    deterministic record via deterministic_records.build_ah_grounded_record instead.

    Args:
        case: Anti-hallucination fixture case dict.
        npc_response: The engine reply already obtained.
        player_id: The player id used for the dialogue call.
    Returns:
        GenerationRecord or None.
    """
    if case.get("expected_verdict") != "refusal":
        return None
    return GenerationRecord(
        record_id=f"{case['id']}:refusal_judge:0",
        source="anti_hallucination",
        npc_id=case["npc_id"],
        player_id=player_id,
        player_message=case["question"],
        npc_response=npc_response,
        criteria=_REFUSAL_CRITERIA,
        judge_kind="refusal_judge",
        expected_polarity="pass_on_yes",
    )
