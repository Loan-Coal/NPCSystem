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
import os
import sys
from pathlib import Path
from typing import Any

import httpx
import yaml

from matchers import evaluate
from report import write_report
from summary import format_summary_lines, summarize


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
        return {
            "case_id": case_id,
            "description": case.get("description", ""),
            "passed": True,
            "expectations": [
                {
                    "kind": "runner",
                    "passed": True,
                    "skipped": True,
                    "detail": "SKIP: no 'input' field — case targets a non-dialogue endpoint, not supported by this runner",
                }
            ],
            "response": None,
            "error": None,
        }

    npc_id = seed.get("npc_id", "npc_eval")
    requires_world = seed.get("requires_world")

    npc_check = client.get(f"{base_url}/v1/graph/nodes/Character/{npc_id}", timeout=10.0)
    if npc_check.status_code == 404:
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


def _setup_reputation(case: dict, client: httpx.Client, base_url: str) -> None:
    """Pre-seed player reputation with a faction before the dialogue call."""
    from datetime import datetime, timezone

    seed = case.get("seed", {})
    player_id = seed.get("player_id", "player_eval")
    faction_id = seed.get("faction_id")
    standing = seed.get("player_reputation_standing")
    if faction_id is None or standing is None:
        return

    check = client.get(f"{base_url}/v1/graph/nodes/Character/{player_id}", timeout=10.0)
    if check.status_code == 404:
        now = datetime.now(timezone.utc).isoformat()
        create_resp = client.post(
            f"{base_url}/v1/graph/nodes/Character",
            json={"properties": {
                "id": player_id,
                "name": player_id,
                "archetype": "player",
                "biography": "The player character.",
                "is_player": True,
                "is_active": True,
                "gossipy": 50,
                "credulity": 50,
                "honesty": 50,
                "current_mood": "neutral",
                "voice_descriptor": None,
                "created_at": now,
                "updated_at": now,
                "last_graph_updated_at": now,
            }},
            timeout=10.0,
        )
        if create_resp.status_code >= 400:
            print(
                f"  [WARN] could not create player node {player_id}: {create_resp.status_code}",
                file=sys.stderr,
            )
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

        for case in cases:
            case_id = case["case_id"]
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

            status = "PASS" if result["passed"] else "FAIL"
            print(f"  {status}")
            results.append(result)

    report_path = write_report(results=results, output_dir=args.reports)
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    run_summary = summarize(results)
    print()
    for line in format_summary_lines(run_summary):
        print(line)
    print(f"\n{passed}/{total} cases passed. Report: {report_path}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
