"""
Module: runner
Layer: evals (standalone eval harness, outside the npc_engine layer model)
Purpose: Orchestrate execution of eval cases against a live engine and record pass/fail results.

runner.py - Eval case runner.

Usage:
    python evals/runner.py [--base-url http://localhost:8000] [--api-key <key>]
                           [--cases evals/cases] [--reports evals/reports]

Exit code 0: all non-skipped expectations passed.
Exit code 1: one or more failures.
Exit code 2: configuration or connectivity error.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
import yaml

import preconditions
from guard_expectations import (
    FALLBACK_LINES,
    GUARD_LORE_RUBRIC,
    GUARD_PREFIXES,
    GUARD_TONE_RUBRIC,
    expected_with_guards,
    guard_expectations,
    is_guard_case,
)
from matchers import EvalConfigError, JudgeResult, evaluate
from report import write_report
from summary import format_summary_lines, summarize
from verdicts import write_verdicts

# Default player id when a case seed omits one (mirrors _run_case / _setup_reputation).
_DEFAULT_PLAYER_ID = "player_eval"

# Guard-case expectations live in guard_expectations.py so the engine runner and the
# null-responder probe score a guard case against the SAME set (ISSUE-256). These names
# are re-exports kept for the existing importers (generation_records, the unit tests
# that pin the prefix scopes); the definitions are in that module.
_GUARD_PREFIXES: tuple[str, ...] = GUARD_PREFIXES
_GUARD_TONE_RUBRIC: str = GUARD_TONE_RUBRIC
_GUARD_LORE_RUBRIC: str = GUARD_LORE_RUBRIC
_FALLBACK_LINES: list[str] = FALLBACK_LINES
_is_guard_case = is_guard_case
_guard_expectations = guard_expectations
_expected_with_guards = expected_with_guards


def _load_cases(cases_dir: Path) -> list[dict]:
    cases = []
    for path in sorted(cases_dir.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            cases.append(yaml.safe_load(f))
    return cases


def _run_case(case: dict, client: httpx.Client, base_url: str) -> dict:
    case_id: str = case["case_id"]
    seed: dict = case.get("seed", {})
    inp: dict | None = case.get("input")

    if inp is None:
        _no_input_detail = (
            "SKIP: no 'input' field — case targets a non-dialogue endpoint, "
            "not supported by this runner"
        )
        return {
            "case_id": case_id,
            "description": case.get("description", ""),
            "passed": True,
            "skipped": True,
            "skip_detail": _no_input_detail,
            "expectations": [
                {
                    "kind": "runner",
                    "passed": True,
                    "skipped": True,
                    "detail": _no_input_detail,
                }
            ],
            "response": None,
            "error": None,
        }

    npc_id = seed.get("npc_id", "npc_eval")
    requires_world = seed.get("requires_world")

    if not preconditions.npc_exists(client, base_url, npc_id):
        world_cmd = (
            "make demo-seed"
            if requires_world == "demo"
            else f"make seed-{requires_world}-world"
            if requires_world
            else "the appropriate seed command"
        )
        skip_detail = f"SKIP: NPC '{npc_id}' not found in graph. Run: {world_cmd}"
        return {
            "case_id": case_id,
            "description": case.get("description", ""),
            "passed": True,
            "skipped": True,
            "skip_detail": skip_detail,
            "expectations": [
                {
                    "kind": "runner",
                    "passed": True,
                    "skipped": True,
                    "detail": skip_detail,
                }
            ],
            "response": None,
            "error": None,
        }

    payload = {
        "player_id": seed.get("player_id", "player_eval"),
        "npc_id": npc_id,
        "player_message": inp["player_message"],
        "location_id": seed.get("location_id"),
        "session_id": f"eval:{case_id}",
    }

    try:
        resp = client.post(f"{base_url}/v1/dialogue", json=payload, timeout=60.0)
        resp.raise_for_status()
        response_body: dict = resp.json()
        error = None
    except Exception as exc:
        response_body = {}
        error = str(exc)

    exp_results: list[dict] = []
    case_passed = True

    for exp in _expected_with_guards(case):
        if exp.get("skip_until_implemented"):
            exp_results.append(
                {
                    "kind": exp["kind"],
                    "passed": True,
                    "skipped": True,
                    "detail": "SKIP (marked skip_until_implemented)",
                }
            )
            continue

        if error:
            exp_results.append(
                {
                    "kind": exp.get("kind", "unknown"),
                    "passed": False,
                    "skipped": False,
                    "detail": f"skipped due to request error: {error}",
                }
            )
            case_passed = False
            continue

        try:
            result = evaluate(expectation=exp, response=response_body)
        except EvalConfigError as cfg_exc:
            exp_results.append(
                {
                    "kind": exp.get("kind", "unknown"),
                    "passed": False,
                    "skipped": False,
                    "detail": f"eval_config_error: {cfg_exc}",
                }
            )
            case_passed = False
            continue

        if isinstance(result, JudgeResult):
            # score=None means the LLM judge was unavailable (timeout / Ollama down).
            # Mark as inconclusive so summary._tally_failures excludes it from content
            # failure counts — an infra outage must never inflate the hallucination tally.
            if result.score is None:
                exp_results.append(
                    {
                        "kind": exp["kind"],
                        "passed": False,
                        "skipped": False,
                        "inconclusive": True,
                        "detail": f"judge_infra_failure: {result.error}",
                    }
                )
                case_passed = False
            else:
                if not result.score:
                    case_passed = False
                exp_results.append(
                    {
                        "kind": exp["kind"],
                        "passed": bool(result.score),
                        "skipped": False,
                        "detail": result.error,
                    }
                )
        else:
            passed, detail = result
            if not passed:
                case_passed = False
            exp_results.append(
                {
                    "kind": exp["kind"],
                    "passed": passed,
                    "skipped": False,
                    "detail": detail,
                }
            )

    return {
        "case_id": case_id,
        "description": case.get("description", ""),
        "passed": case_passed and error is None,
        "expectations": exp_results,
        "response": response_body or None,
        "error": error,
    }


def _setup_reputation(case: dict, client: httpx.Client, base_url: str) -> None:
    """Pre-seed player reputation with a faction before the dialogue call.

    The player node itself is created up-front by ``preconditions.ensure_player_node``
    in ``main()`` (strict-player policy), so this only issues the reputation PUT.
    """
    seed = case.get("seed", {})
    player_id = seed.get("player_id", _DEFAULT_PLAYER_ID)
    faction_id = seed.get("faction_id")
    standing = seed.get("player_reputation_standing")
    if faction_id is None or standing is None:
        return

    resp = client.put(
        f"{base_url}/v1/admin/characters/{player_id}/reputation/{faction_id}",
        json={"standing": standing},
        timeout=10.0,
    )
    if resp.status_code >= 400:
        print(
            f"  [WARN] reputation setup failed for {player_id}/{faction_id}: {resp.status_code}",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NPC Engine eval runner")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=os.getenv("API_KEY_SECRET", "eval-key-change-me"))
    parser.add_argument("--cases", default="evals/cases", type=Path)
    parser.add_argument("--reports", default="evals/reports", type=Path)
    parser.add_argument(
        "--reset-world",
        action="store_true",
        help="Reset world_state to the age_of_peace baseline before the run (default off).",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Also write raw per-case verdicts as JSON to this path (DEC-153 §7).",
    )
    args = parser.parse_args(argv)

    cases = _load_cases(args.cases)
    if not cases:
        print(f"No eval cases found in {args.cases}", file=sys.stderr)
        return 2

    headers = {"Authorization": f"Bearer {args.api_key}"}
    results: list[dict] = []

    with httpx.Client(headers=headers) as client:
        try:
            health = client.get(f"{args.base_url}/health", timeout=5.0)
            health.raise_for_status()
        except Exception as exc:
            print(f"Server not reachable at {args.base_url}: {exc}", file=sys.stderr)
            return 2

        if args.reset_world:
            preconditions.reset_world(client, args.base_url, preconditions.WorldBaseline())

        for case in cases:
            case_id = case["case_id"]
            player_id = case.get("seed", {}).get("player_id", _DEFAULT_PLAYER_ID)
            preconditions.ensure_player_node(client, args.base_url, player_id)
            _setup_reputation(case=case, client=client, base_url=args.base_url)

            print(f"  running {case_id} ...")
            result = _run_case(case=case, client=client, base_url=args.base_url)

            inp = case.get("input")
            if inp:
                print(f"    > {inp['player_message']!r}")
            if result.get("response"):
                npc_text = result["response"].get("npc_response", "") or ""
                truncated = (npc_text[:120] + "...") if len(npc_text) > 120 else npc_text
                print(f"    < {truncated!r}")
            for exp_result in result.get("expectations", []):
                if exp_result.get("skipped"):
                    continue
                mark = "PASS" if exp_result["passed"] else "FAIL"
                detail = f": {exp_result['detail']}" if not exp_result["passed"] else ""
                print(f"    [{mark}] {exp_result['kind']}{detail}")

            if result.get("skipped"):
                print(f"  SKIP: {result.get('skip_detail', 'case skipped')}")
            else:
                status = "PASS" if result["passed"] else "FAIL"
                print(f"  {status}")
            results.append(result)

    report_path = write_report(results=results, output_dir=args.reports)
    if args.json_out is not None:
        verdicts_path = write_verdicts(results, args.json_out, source="runner")
        print(f"Verdicts: {verdicts_path}")
    non_skipped = [r for r in results if not r.get("skipped")]
    skipped_count = len(results) - len(non_skipped)
    passed = sum(1 for r in non_skipped if r["passed"])
    total = len(non_skipped)

    run_summary = summarize(results)
    print()
    for line in format_summary_lines(run_summary):
        print(line)
    print(f"\n{passed}/{total} cases passed, {skipped_count} skipped. Report: {report_path}")

    if not run_summary.guarantee_demonstrated:
        print(
            "  [FAIL] anti-hallucination guarantee not demonstrated "
            f"(guard_turns={run_summary.guard_turns}, "
            f"hallucinations={run_summary.hallucination_failures})",
            file=sys.stderr,
        )
        return 1

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
