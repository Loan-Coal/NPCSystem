"""
Module: generate_runner
Layer: evals (eval harness — not part of src/)
Purpose: Generation pass of the two-phase eval pipeline. Calls /v1/dialogue for every
         expectation (LLM-judge and deterministic alike), captures retrieval context,
         and writes gen-dir output {meta.json,outputs.jsonl} or a legacy TranscriptFile
         for the judge pass. Record construction lives in generation_records and the
         HTTP collection loop in generation_collection; this module owns the CLI and
         the decision of what gets written where.
Dependencies: httpx, argparse, logging, os, pathlib, sys; runner,
         anti_hallucination_runner, generation_collection, paired_arms, eval_records,
         run_config
Used by: Makefile eval-generate target, judge_runner (reads transcript it writes)
Does NOT: call the LLM judge, modify graph state, import from src/npc_engine/
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import httpx

from eval_records import write_generation_dir, write_transcript
from generation_collection import collect_records
from paired_arms import PairedArmsError, parse_profiles, run_paired
from run_config import _DEFAULT_RETRIEVAL_PROFILE, RunConfig, resolve_run_config

# Stable private helpers from sibling runners; generate_runner is sole two-phase consumer.
from anti_hallucination_runner import _load_fixture
from runner import _load_cases

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL: str = "http://localhost:8000"
_TRANSCRIPT_STEM: str = "eval_generation"

_logger = logging.getLogger(__name__)


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
    cases_dir: Path | None = None,
    config: RunConfig | None = None,
    retrieval_profile: str | None = None,
) -> Path:
    """Collect records and write output to either gen-dir or legacy transcript.

    gen_id non-empty: <out_dir>/<gen_id>/{meta.json,outputs.jsonl}.
    gen_id empty: legacy TranscriptFile at <out_dir>/<stem>_<run_id>.json.

    A gen-dir run always records a RunConfig in meta.json. Resolving it is what makes
    the artifact reproducible — prompt version, generation model and sampling params,
    judge model, git SHA and golden-set hash. It is resolved here rather than in main()
    so that every caller of run() gets it, and it is resolved *before* the (slow)
    generation pass so a misconfigured run fails in seconds rather than after an hour.

    Args:
        yaml_cases, ah_cases: Eval cases to process.
        client: Active httpx.Client.
        base_url: Engine base URL.
        out_dir: Base output directory.
        run_id: Identifier for the legacy filename.
        gen_id: Non-empty selects gen-dir format.
        k: Repetitions per case.
        cases_dir: Case directory used to compute golden_set_version; defaults to
            evals/cases/ when omitted.
        config: Pre-resolved run config; resolved from the live repo when omitted.
    Returns:
        Path to the written output.
    Raises:
        JudgeModelCollisionError: If the judge model equals the generation model.
        GoldenSetVersionError: If cases_dir is empty or missing.
    """
    resolved_config = config
    if gen_id and resolved_config is None:
        resolved_config = resolve_run_config(
            cases_dir=cases_dir,
            retrieval_profile=retrieval_profile or _DEFAULT_RETRIEVAL_PROFILE,
        )
    records = collect_records(yaml_cases, ah_cases, client, base_url, k=k, retrieval_profile=retrieval_profile)
    if gen_id:
        gen_dir = out_dir / gen_id
        write_generation_dir(gen_dir, records, gen_id=gen_id, k=k, config=resolved_config)
        return gen_dir
    path = out_dir / f"{_TRANSCRIPT_STEM}_{run_id}.json"
    write_transcript(path, records)
    return path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _validated_profiles(args: argparse.Namespace) -> tuple[str, ...] | None:
    """Resolve --profiles into arm names, or None for an ordinary single-arm run.

    Args:
        args: Parsed CLI namespace.
    Returns:
        Arm names, or None when --profiles was not given.
    Raises:
        PairedArmsError: When --profiles is combined with --retrieval-profile (two ways
            to name the arm is one way for them to disagree), when --gen-id is missing
            (the legacy transcript format has nowhere to put a second arm), or when the
            list itself is not a paired design.
    """
    if args.profiles is None:
        return None
    if args.retrieval_profile is not None:
        raise PairedArmsError("--profiles and --retrieval-profile are mutually exclusive.")
    if not args.gen_id:
        raise PairedArmsError("--profiles requires --gen-id: each arm needs its own gen dir.")
    # Annotated local: evals/ is not on mypy_path, so sibling imports type as Any
    # (pyproject mypy_path = "src"). The annotation restores the checked type here.
    names: tuple[str, ...] = parse_profiles(str(args.profiles))
    return names


def _report_arms(arms: tuple[Path, ...]) -> None:
    """Print each arm's directory plus the compare command that pairs them."""
    for arm in arms:
        print(f"Arm written: {arm}")
    if len(arms) == 2:
        print(f"Compare with: python -m evals compare {arms[0]} {arms[1]}")


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
    parser.add_argument(
        "--retrieval-profile",
        default=None,
        help=(
            "Named retrieval configuration every turn is generated under (the A/B arm). "
            "Omitted by default so the request is byte-identical to a pre-profile run."
        ),
    )
    parser.add_argument(
        "--profiles",
        default=None,
        help=(
            "Comma-separated profiles to run as PAIRED ARMS inside one generation, e.g. "
            "'default,aggressive'. Every case runs under every profile back to back, and "
            "each arm is written to <gen-id>__<profile>/. --k is repetitions per arm. "
            "Requires --gen-id; mutually exclusive with --retrieval-profile."
        ),
    )
    args = parser.parse_args(argv)
    profiles = _validated_profiles(args)

    headers = {"Authorization": f"Bearer {args.api_key}"}
    with httpx.Client(headers=headers) as client:
        try:
            client.get(f"{args.base_url}/health", timeout=5.0).raise_for_status()
        except Exception as exc:
            print(f"Server not reachable at {args.base_url}: {exc}", file=sys.stderr)
            return 2

        yaml_cases = _load_cases(args.cases)
        ah_cases = _load_fixture(args.fixture) if args.fixture.exists() else []
        if profiles is not None:
            arms = run_paired(
                yaml_cases=yaml_cases, ah_cases=ah_cases, client=client,
                base_url=args.base_url, out_dir=args.out, gen_id=args.gen_id, k=args.k,
                profiles=profiles, cases_dir=args.cases,
            )
            _report_arms(arms)
            return 0
        path = run(
            yaml_cases=yaml_cases,
            ah_cases=ah_cases,
            client=client,
            base_url=args.base_url,
            out_dir=args.out,
            run_id=args.run_id,
            gen_id=args.gen_id,
            k=args.k,
            cases_dir=args.cases,
            retrieval_profile=args.retrieval_profile,
        )

    print(f"Transcript written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
