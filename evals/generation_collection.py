"""
Module: generation_collection
Layer: evals (eval harness — not part of src/)
Purpose: The HTTP collection loop of the generation pass — one /v1/dialogue call per
         expectation, with the per-repetition metadata (duration, context receipt, and
         the deprecated retrieval approximation) stamped onto each frozen record.
Dependencies: httpx, logging, time; generation_records, deterministic_records,
         preconditions, anti_hallucination_runner, eval_records, context_capture,
         context_receipt_record
Used by: generate_runner (CLI and gen-dir writing), paired_arms (per-arm collection)
Does NOT: parse CLI arguments, write files, call the LLM judge, or import from
         src/npc_engine/.

Split out of generate_runner.py, which owned both the collection loop and the CLI and
had reached the 300-line cap. SRP: this module is the collector, generate_runner is the
handler/orchestrator.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

import deterministic_records
import generation_records
import preconditions
from context_capture import capture_retrieval_context
from context_receipt_record import parse_context_receipt
from eval_records import GenerationRecord

# Stable private helpers from a sibling runner; the two-phase pipeline is its sole consumer.
from anti_hallucination_runner import _PLAYER_ID as _AH_PLAYER_ID

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PLAYER_ID: str = "player_eval"

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core collection loop
# ---------------------------------------------------------------------------


def post_dialogue(
    case_npc_id: str, player_id: str, message: str, client: httpx.Client, base_url: str,
    retrieval_profile: str | None = None,
) -> dict[str, Any]:
    """POST /v1/dialogue and return the full parsed response body (empty dict on error).

    Logs the error with the NPC identity before returning so a request failure is
    distinguishable from a genuine empty response.

    Deterministic matchers (in_set, range, schema) check fields beyond npc_response
    (facial_expression.type, action.type, relation_deltas.*), so the whole body must
    be preserved for EVAL-P6.1's deterministic records to replay faithfully.
    """
    try:
        resp = client.post(
            f"{base_url}/v1/dialogue",
            json={
                "player_id": player_id,
                "npc_id": case_npc_id,
                "player_message": message,
                # Reporting switch only. Pinned engine-side by
                # test_asking_for_a_receipt_does_not_change_the_prompt: it never reaches
                # context assembly or prompt building, so generated text is unaffected.
                "include_context_receipt": True,
                # Omitted entirely when None so the request stays byte-identical to what
                # pre-profile runs sent, and the engine applies its declared default.
                **({"retrieval_profile": retrieval_profile} if retrieval_profile else {}),
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return dict(resp.json())
    except Exception as exc:
        _logger.warning("post_dialogue failed npc_id=%s player_id=%s: %s", case_npc_id, player_id, exc)
        return {}


def stamp_records(
    records: list[GenerationRecord], *, rep: int, duration_ms: int, retrieved: tuple,
    receipt: object = None,
) -> list[GenerationRecord]:
    """Copy each record with the per-repetition fields filled in (records are frozen)."""
    update = {
        "repetition": rep, "duration_ms": duration_ms, "retrieved_context": retrieved,
        "context_receipt": receipt,
    }
    return [r.model_copy(update=update) for r in records]


def collect_yaml_case_records(
    case: dict, client: httpx.Client, base_url: str, rep: int, retrieval_profile: str | None = None,
) -> list[GenerationRecord]:
    """Call /v1/dialogue for one YAML case and build its judge + deterministic records.

    Returns an empty list, without calling the engine, when the case's NPC has no
    Character node in the graph — the world its seed declares was never seeded
    (ISSUE-284: the shared world guard, preconditions.npc_exists, used by both eval
    verbs so this path can no longer generate a record against a nonexistent NPC).
    """
    inp = case.get("input")
    if inp is None:
        return []
    seed = case.get("seed", {})
    npc_id = seed.get("npc_id", "")
    if not preconditions.npc_exists(client, base_url, npc_id):
        _logger.info(
            "case skipped: NPC not found in graph (world not seeded) case_id=%s npc_id=%s requires_world=%s",
            case.get("case_id", ""), npc_id, seed.get("requires_world"),
        )
        return []
    player_id = seed.get("player_id", DEFAULT_PLAYER_ID)
    preconditions.ensure_player_node(client, base_url, player_id)
    player_message = inp["player_message"]

    t0 = time.perf_counter()
    response = post_dialogue(npc_id, player_id, player_message, client, base_url, retrieval_profile)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    retrieved = capture_retrieval_context(client, base_url, npc_id, player_message)

    records = generation_records.build_yaml_case_records(case, response, default_player_id=DEFAULT_PLAYER_ID)
    return stamp_records(records, rep=rep, duration_ms=duration_ms, retrieved=retrieved,
                  receipt=parse_context_receipt(response.get("context_receipt")))


def collect_ah_case_records(
    case: dict, client: httpx.Client, base_url: str, rep: int, retrieval_profile: str | None = None,
) -> list[GenerationRecord]:
    """Call /v1/dialogue for one AH fixture case and build its refusal/grounded record."""
    t0 = time.perf_counter()
    response = post_dialogue(case["npc_id"], _AH_PLAYER_ID, case["question"], client, base_url, retrieval_profile)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    retrieved = capture_retrieval_context(client, base_url, case["npc_id"], case["question"])
    npc_response = response.get("npc_response", "") or ""

    records = [
        r
        for r in (
            generation_records.build_ah_refusal_record(case, npc_response, player_id=_AH_PLAYER_ID),
            deterministic_records.build_ah_grounded_record(case, response, player_id=_AH_PLAYER_ID),
        )
        if r is not None
    ]
    return stamp_records(records, rep=rep, duration_ms=duration_ms, retrieved=retrieved,
                  receipt=parse_context_receipt(response.get("context_receipt")))


def collect_records(
    yaml_cases: list[dict],
    ah_cases: list[dict],
    client: httpx.Client,
    base_url: str,
    k: int = 1,
    retrieval_profile: str | None = None,
) -> list[GenerationRecord]:
    """Generate dialogue responses and build records for every covered expectation.

    Each case runs k times; each repetition captures duration_ms and a retrieval
    context approximation from GET /v1/admin/debug/retrieval. YAML cases first
    (judge + deterministic records, EVAL-P6.1), then AH cases (refusal cases get a
    refusal_judge record; grounded cases get a deterministic anti_hallucination_grounded
    record — no case type is dropped from the transcript).

    Args:
        yaml_cases: Loaded YAML eval cases.
        ah_cases: Loaded anti-hallucination fixture cases.
        client: Active httpx.Client with auth headers.
        base_url: NPC engine base URL.
        k: Number of repetitions per case (default 1).
        retrieval_profile: Profile every turn is generated under; None applies the
            engine's declared default and sends no field at all.
    Returns:
        List of GenerationRecords for every judge and deterministic expectation.
    """
    records: list[GenerationRecord] = []
    for rep in range(k):
        for case in yaml_cases:
            records.extend(collect_yaml_case_records(case, client, base_url, rep, retrieval_profile))
        for case in ah_cases:
            records.extend(collect_ah_case_records(case, client, base_url, rep, retrieval_profile))
    return records
