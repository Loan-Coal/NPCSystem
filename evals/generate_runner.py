"""
Module: generate_runner
Layer: evals (eval harness — not part of src/)
Purpose: Generation pass of the two-phase eval pipeline. POSTs /v1/dialogue for every
         LLM-judge expectation in the YAML case suite and every refusal case in the
         anti-hallucination fixture, writing one TranscriptFile for the judge pass.
Dependencies: httpx, argparse, pathlib, sys; runner (load_cases), matchers (criteria
         templates), anti_hallucination_runner (_load_fixture), preconditions,
         eval_records (GenerationRecord, write_transcript)
Used by: Makefile eval-generate target, judge_runner (reads the transcript it writes)
Does NOT: call the LLM judge, modify graph state, import from src/npc_engine/
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import httpx

import preconditions
from eval_records import GenerationRecord, write_transcript
from matchers import _AFFIRMATION_CRITERIA_TMPL, _REFUSAL_CRITERIA

# Reuse private helpers from sibling runners (same evals/ package on pythonpath).
# These are stable internal APIs; generate_runner is the only two-phase consumer.
from anti_hallucination_runner import _PLAYER_ID as _AH_PLAYER_ID
from anti_hallucination_runner import _load_fixture
from runner import _expected_with_guards, _load_cases

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LLM_JUDGE_KINDS: frozenset[str] = frozenset({"tone_judge", "affirms_judge"})
_DEFAULT_PLAYER_ID: str = "player_eval"
_DEFAULT_BASE_URL: str = "http://localhost:8000"
_TRANSCRIPT_STEM: str = "eval_generation"


# ---------------------------------------------------------------------------
# Criteria derivation helpers
# ---------------------------------------------------------------------------


def _criteria_for_tone(exp: dict) -> str:
    """Extract the judge criteria string from a tone_judge expectation."""
    return exp.get("judge_prompt") or exp.get("description", "")


def _criteria_for_affirms(exp: dict) -> str:
    """Derive the criteria string for an affirms_judge expectation.

    Mirrors the derivation in matchers._eval_affirms_judge so the judge_runner
    can call _run_binary_judge(criteria, content) identically to the inline runner.
    """
    claim = exp.get("claim")
    if claim:
        return _AFFIRMATION_CRITERIA_TMPL.format(claim=str(claim).strip())
    return exp.get("description", "")


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------


def _build_yaml_records_for_case(
    case: dict,
    npc_response: str,
) -> list[GenerationRecord]:
    """Build one GenerationRecord per LLM-judge expectation in a YAML case.

    Non-judge expectations (min_length, keyword_none, schema, etc.) are not
    represented here; they remain in runner.py's inline pass.

    Args:
        case: YAML eval case dict (case_id, seed, input, expected).
        npc_response: The engine reply already obtained for this case.
    Returns:
        List of GenerationRecords, one per tone_judge/affirms_judge expectation.
    """
    records: list[GenerationRecord] = []
    case_id: str = case.get("case_id", "")
    npc_id: str = case.get("seed", {}).get("npc_id", "")
    player_id: str = case.get("seed", {}).get("player_id", _DEFAULT_PLAYER_ID)

    for i, exp in enumerate(_expected_with_guards(case)):
        kind = exp.get("kind", "")
        if kind not in _LLM_JUDGE_KINDS:
            continue

        if kind == "tone_judge":
            criteria = _criteria_for_tone(exp)
            polarity = "pass_on_yes"
        else:  # affirms_judge
            criteria = _criteria_for_affirms(exp)
            polarity = "pass_on_no"

        records.append(
            GenerationRecord(
                record_id=f"{case_id}:{kind}:{i}",
                source="runner",
                npc_id=npc_id,
                player_id=player_id,
                player_message=case.get("input", {}).get("player_message", ""),
                npc_response=npc_response,
                criteria=criteria,
                judge_kind=kind,
                expected_polarity=polarity,
            )
        )
    return records


def _build_ah_record(case: dict, npc_response: str) -> GenerationRecord | None:
    """Build a GenerationRecord for one anti-hallucination fixture case.

    Returns a refusal_judge record when expected_verdict == "refusal".
    Returns None for grounded cases (deterministic substring check; no LLM judge).

    Args:
        case: Anti-hallucination fixture case dict.
        npc_response: The engine reply already obtained.
    Returns:
        GenerationRecord or None.
    """
    if case.get("expected_verdict") != "refusal":
        return None
    return GenerationRecord(
        record_id=f"{case['id']}:refusal_judge:0",
        source="anti_hallucination",
        npc_id=case["npc_id"],
        player_id=_AH_PLAYER_ID,
        player_message=case["question"],
        npc_response=npc_response,
        criteria=_REFUSAL_CRITERIA,
        judge_kind="refusal_judge",
        expected_polarity="pass_on_yes",
    )


# ---------------------------------------------------------------------------
# Core collection loop
# ---------------------------------------------------------------------------


def _post_dialogue(case_npc_id: str, player_id: str, message: str, client: httpx.Client, base_url: str) -> str:
    """POST /v1/dialogue and return the npc_response string (empty on error)."""
    try:
        resp = client.post(
            f"{base_url}/v1/dialogue",
            json={"player_id": player_id, "npc_id": case_npc_id, "player_message": message},
            timeout=60.0,
        )
        resp.raise_for_status()
        return str(resp.json().get("npc_response", ""))
    except Exception:
        return ""


def collect_records(
    yaml_cases: list[dict],
    ah_cases: list[dict],
    client: httpx.Client,
    base_url: str,
) -> list[GenerationRecord]:
    """Generate dialogue responses and build records for all LLM-judge cases.

    Calls ensure_player_node per YAML case. Processes YAML cases first, then
    anti-hallucination refusal cases (grounded cases are excluded — deterministic).

    Args:
        yaml_cases: Loaded YAML eval cases (from runner._load_cases).
        ah_cases: Loaded anti-hallucination fixture cases (from _load_fixture).
        client: Active httpx.Client with auth headers.
        base_url: NPC engine base URL.
    Returns:
        List of GenerationRecords for all LLM-judge expectations.
    """
    records: list[GenerationRecord] = []

    for case in yaml_cases:
        inp = case.get("input")
        if inp is None:
            continue
        player_id = case.get("seed", {}).get("player_id", _DEFAULT_PLAYER_ID)
        preconditions.ensure_player_node(client, base_url, player_id)

        npc_id = case.get("seed", {}).get("npc_id", "")
        npc_response = _post_dialogue(npc_id, player_id, inp["player_message"], client, base_url)
        records.extend(_build_yaml_records_for_case(case, npc_response))

    for case in ah_cases:
        npc_response = _post_dialogue(case["npc_id"], _AH_PLAYER_ID, case["question"], client, base_url)
        record = _build_ah_record(case, npc_response)
        if record is not None:
            records.append(record)

    return records


def run(
    yaml_cases: list[dict],
    ah_cases: list[dict],
    client: httpx.Client,
    base_url: str,
    out_dir: Path,
    run_id: str,
) -> Path:
    """Collect records and write one TranscriptFile.

    Args:
        yaml_cases: YAML eval cases.
        ah_cases: Anti-hallucination fixture cases.
        client: Active httpx.Client.
        base_url: Engine base URL.
        out_dir: Directory for the transcript file.
        run_id: Unique run identifier (used in the filename).
    Returns:
        Path to the written transcript file.
    """
    records = collect_records(yaml_cases, ah_cases, client, base_url)
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
    parser.add_argument("--out", default="e2e/transcripts", type=Path)
    parser.add_argument("--run-id", default="latest")
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
        )

    print(f"Transcript written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
