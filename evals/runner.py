"""
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
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import yaml

from matchers import evaluate
from report import write_report


def _load_cases(cases_dir: Path) -> list[dict]:
    cases = []
    for path in sorted(cases_dir.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            cases.append(yaml.safe_load(f))
    return cases


def _run_case(case: dict, client: httpx.Client, base_url: str) -> dict:
    case_id: str = case["case_id"]
    seed: dict = case.get("seed", {})
    inp: dict = case["input"]

    payload = {
        "player_id": seed.get("player_id", "player_eval"),
        "npc_id": seed.get("npc_id", "npc_eval"),
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

    for exp in case.get("expected", []):
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

        passed, detail = evaluate(expectation=exp, response=response_body)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NPC Engine eval runner")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default="eval-key-change-me")
    parser.add_argument("--cases", default="evals/cases", type=Path)
    parser.add_argument("--reports", default="evals/reports", type=Path)
    args = parser.parse_args(argv)

    cases = _load_cases(args.cases)
    if not cases:
        print(f"No eval cases found in {args.cases}", file=sys.stderr)
        return 2

    headers = {"X-API-Key": args.api_key}
    results: list[dict] = []

    with httpx.Client(headers=headers) as client:
        try:
            health = client.get(f"{args.base_url}/health", timeout=5.0)
            health.raise_for_status()
        except Exception as exc:
            print(f"Server not reachable at {args.base_url}: {exc}", file=sys.stderr)
            return 2

        for case in cases:
            print(f"  running {case['case_id']} ...", end=" ", flush=True)
            result = _run_case(case=case, client=client, base_url=args.base_url)
            status = "PASS" if result["passed"] else "FAIL"
            print(status)
            results.append(result)

    report_path = write_report(results=results, output_dir=args.reports)
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n{passed}/{total} cases passed. Report: {report_path}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
