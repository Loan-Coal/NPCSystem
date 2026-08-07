"""
Module: generate_runner
Layer: evals (eval harness — not part of src/)
Purpose: Generation pass of the two-phase eval pipeline. Calls /v1/dialogue for every
         expectation (LLM-judge and deterministic alike), captures retrieval context,
         and writes gen-dir output {meta.json,outputs.jsonl} or a legacy TranscriptFile
         for the judge pass. Record construction (judge, deterministic, AH) lives in
         generation_records; this module owns the HTTP collection loop and CLI.
Dependencies: httpx, argparse, pathlib, sys, time; runner, generation_records,
         deterministic_records, anti_hallucination_runner, preconditions, eval_records,
         context_capture
Used by: Makefile eval-generate target, judge_runner (reads transcript it writes)
Does NOT: call the LLM judge, modify graph state, import from src/npc_engine/
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any
import httpx

import deterministic_records
import generation_records
import preconditions
from context_capture import capture_retrieval_context
from eval_records import GenerationRecord, write_generation_dir, write_transcript

# Stable private helpers from sibling runners; generate_runner is sole two-phase consumer.
from anti_hallucination_runner import _PLAYER_ID as _AH_PLAYER_ID
from anti_hallucination_runner import _load_fixture
from runner import _load_cases

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_PLAYER_ID: str = "player_eval"
_DEFAULT_BASE_URL: str = "http://localhost:8000"
_TRANSCRIPT_STEM: str = "eval_generation"


# ---------------------------------------------------------------------------
# Core collection loop
# ---------------------------------------------------------------------------


def _post_dialogue(case_npc_id: str, player_id: str, message: str, client: httpx.Client, base_url: str) -> dict[str, Any]:
    """POST /v1/dialogue and return the full parsed response body (empty dict on error).

    Deterministic matchers (in_set, range, schema) check fields beyond npc_response
    (facial_expression.type, action.type, relation_deltas.*), so the whole body must
    be preserved for EVAL-P6.1's deterministic records to replay faithfully.
    """
    try:
        resp = client.post(
            f"{base_url}/v1/dialogue",
            json={"player_id": player_id, "npc_id": case_npc_id, "player_message": message},
            timeout=60.0,
        )
        resp.raise_for_status()
        return dict(resp.json())
    except Exception:
        return {}


def _stamp(records: list[GenerationRecord], *, rep: int, duration_ms: int, retrieved: tuple) -> list[GenerationRecord]:
    """Copy each record with the per-repetition fields filled in (records are frozen)."""
    update = {"repetition": rep, "duration_ms": duration_ms, "retrieved_context": retrieved}
    return [r.model_copy(update=update) for r in records]


def _collect_yaml_case_records(
    case: dict, client: httpx.Client, base_url: str, rep: int
) -> list[GenerationRecord]:
    """Call /v1/dialogue for one YAML case and build its judge + deterministic records."""
    inp = case.get("input")
    if inp is None:
        return []
    player_id = case.get("seed", {}).get("player_id", _DEFAULT_PLAYER_ID)
    preconditions.ensure_player_node(client, base_url, player_id)
    npc_id = case.get("seed", {}).get("npc_id", "")
    player_message = inp["player_message"]

    t0 = time.perf_counter()
    response = _post_dialogue(npc_id, player_id, player_message, client, base_url)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    retrieved = capture_retrieval_context(client, base_url, npc_id, player_message)

    records = generation_records.build_yaml_case_records(case, response, default_player_id=_DEFAULT_PLAYER_ID)
    return _stamp(records, rep=rep, duration_ms=duration_ms, retrieved=retrieved)


def _collect_ah_case_records(case: dict, client: httpx.Client, base_url: str, rep: int) -> list[GenerationRecord]:
    """Call /v1/dialogue for one AH fixture case and build its refusal/grounded record."""
    t0 = time.perf_counter()
    response = _post_dialogue(case["npc_id"], _AH_PLAYER_ID, case["question"], client, base_url)
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
    return _stamp(records, rep=rep, duration_ms=duration_ms, retrieved=retrieved)


def collect_records(
    yaml_cases: list[dict],
    ah_cases: list[dict],
    client: httpx.Client,
    base_url: str,
    k: int = 1,
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
    Returns:
        List of GenerationRecords for every judge and deterministic expectation.
    """
    records: list[GenerationRecord] = []
    for rep in range(k):
        for case in yaml_cases:
            records.extend(_collect_yaml_case_records(case, client, base_url, rep))
        for case in ah_cases:
            records.extend(_collect_ah_case_records(case, client, base_url, rep))
    return records


def run(
    yaml_cases: list[dict],
    ah_cases: list[dict],
    client: httpx.Client,
    base_url: str,
    out_dir: Path,
    run_id: str,
    *,
    gen_id: str = "",
    k: int = 1,
) -> Path:
    """Collect records and write output to either gen-dir or legacy transcript.

    gen_id non-empty: <out_dir>/<gen_id>/{meta.json,outputs.jsonl}.
    gen_id empty: legacy TranscriptFile at <out_dir>/<stem>_<run_id>.json.

    Args:
        yaml_cases, ah_cases: Eval cases to process.
        client: Active httpx.Client.
        base_url: Engine base URL.
        out_dir: Base output directory.
        run_id: Identifier for the legacy filename.
        gen_id: Non-empty selects gen-dir format.
        k: Repetitions per case.
    Returns:
        Path to the written output.
    """
    records = collect_records(yaml_cases, ah_cases, client, base_url, k=k)
    if gen_id:
        gen_dir = out_dir / gen_id
        write_generation_dir(gen_dir, records, gen_id=gen_id, k=k)
        return gen_dir
    path = out_dir / f"{_TRANSCRIPT_STEM}_{run_id}.json"
    write_transcript(path, records)
    return path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Parse args and run the generation pass.

    Args:
        argv: CLI argument list (defaults to sys.argv[1:]).
    Returns:
        Exit code (0 on success, 2 on connectivity error).
    """
    parser = argparse.ArgumentParser(description="NPC Engine eval generation pass")
    parser.add_argument("--base-url", default=_DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=os.getenv("API_KEY_SECRET", "eval-key-change-me"))
    parser.add_argument("--cases", default="evals/cases", type=Path)
    parser.add_argument("--fixture", default="evals/cases/anti_hallucination_demo.json", type=Path)
    parser.add_argument("--out", default="evals/generations", type=Path)
    parser.add_argument("--run-id", default="latest")
    parser.add_argument("--gen-id", default="", dest="gen_id")
    parser.add_argument("--k", default=1, type=int)
    args = parser.parse_args(argv)

    headers = {"Authorization": f"Bearer {args.api_key}"}
    with httpx.Client(headers=headers) as client:
        try:
            client.get(f"{args.base_url}/health", timeout=5.0).raise_for_status()
        except Exception as exc:
            print(f"Server not reachable at {args.base_url}: {exc}", file=sys.stderr)
            return 2

        yaml_cases = _load_cases(args.cases)
        ah_cases = _load_fixture(args.fixture) if args.fixture.exists() else []
        path = run(
            yaml_cases=yaml_cases,
            ah_cases=ah_cases,
            client=client,
            base_url=args.base_url,
            out_dir=args.out,
            run_id=args.run_id,
            gen_id=args.gen_id,
            k=args.k,
        )

    print(f"Transcript written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
