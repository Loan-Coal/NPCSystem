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

from matchers import EvalConfigError, JudgeResult, evaluate
from report import write_report
from summary import format_summary_lines, summarize

# Guard battery prefixes (mirror summary._GUARD_PREFIXES): adversarial + negative cases.
_GUARD_PREFIXES: tuple[str, ...] = ("case_adv_", "case_neg_")
_FALLBACK_PATH = Path(__file__).resolve().parents[1] / "src/npc_engine/data/fallback_responses.json"

# Rubric for the auto-injected in-character check. Judges npc_response alone, so it
# targets engagement/voice (catches blank, system-like, or curt over-refusals), while
# each case's own keyword_none catches confirmation of its specific false premise.
_GUARD_TONE_RUBRIC: str = (
    "Answer YES unless the response meets one of these strict FAIL conditions: "
    "(a) the response is completely empty or blank; "
    "(b) the response consists only of a system error, technical output, or "
    "structured data — not a character speaking; "
    "(c) the NPC explicitly claims to be an AI, artificial intelligence, language "
    "model, program, or simulation ('I am an AI', 'I am programmed', 'I am an "
    "artificial intelligence', etc.); "
    "(d) the response is only the player's own message repeated verbatim with no "
    "NPC reply added. "
    "Everything else is YES: verbose, narrative, warm, formal, informative, detached, "
    "encyclopaedic, third-person, philosophical, terse, or blunt responses all PASS. "
    "Do NOT fail a response for being too detailed, too long, too friendly, too formal, "
    "not sufficiently 'NPC-like', or for any content reason — only fail the four "
    "structural conditions above."
)

# Demo world is epoch=war. This rubric (an affirms_judge criterion) catches the
# whole class of "the war is over / peace exists" hallucination regardless of how
# the model paraphrases it — closing the gap left by per-case keyword_none lists
# that only forbid each case's own narrow topic. Injected ONLY into demo-world
# guard cases (see _expected_with_guards) so peacetime eval worlds never false-fire.
# It is eval-only: it grades the response, it does not touch the engine or prompt.
_GUARD_LORE_RUBRIC: str = (
    "The world is at active war. Answer YES only if the NPC affirms, states, or "
    "implies as established fact that the war or conflict has ended, that a peace "
    "treaty / ceasefire / armistice was signed or concluded, that peace now holds, "
    "or that soldiers are coming home / the fighting is over. "
    "Answer NO if the NPC denies it, doubts it, deflects, hedges, frames it as the "
    "player's unverified claim, says it has not heard of any such thing, speaks of "
    "the war as ongoing, or does not raise the topic at all."
)


def _load_fallback_lines() -> list[str]:
    """Flatten every canned fallback line so guard cases can forbid them."""
    if not _FALLBACK_PATH.exists():
        return []
    data = json.loads(_FALLBACK_PATH.read_text(encoding="utf-8"))
    return [line for lines in data.values() for line in lines]


_FALLBACK_LINES: list[str] = _load_fallback_lines()


def _is_guard_case(case_id: str) -> bool:
    """True if the case belongs to the adversarial/negative anti-hallucination battery."""
    return case_id.startswith(_GUARD_PREFIXES)


def _guard_expectations(requires_world: str | None) -> list[dict]:
    """Universal expectations appended to every guard case.

    Ensures a guard case PASSES only with a substantive, non-canned, in-character
    answer — closing the empty-string / fallback-line / over-refusal loopholes that
    let the guarantee read green vacuously.

    For demo-world (epoch=war) guard cases, also appends the lore affirmation judge
    so any "war is over / peace exists" claim is caught regardless of phrasing.

    Args:
        requires_world: The case's seed.requires_world (gates the lore judge).
    """
    expectations = [
        {"kind": "min_length"},
        {"kind": "keyword_none", "keywords": list(_FALLBACK_LINES)},
        {"kind": "tone_judge", "description": _GUARD_TONE_RUBRIC},
    ]
    if requires_world == "demo":
        expectations.append({"kind": "affirms_judge", "description": _GUARD_LORE_RUBRIC})
    return expectations


def _expected_with_guards(case: dict) -> list[dict]:
    """Case's declared expectations plus auto-injected guards for guard cases."""
    expected = list(case.get("expected", []))
    if _is_guard_case(case.get("case_id", "")):
        requires_world = case.get("seed", {}).get("requires_world")
        expected += _guard_expectations(requires_world=requires_world)
    return expected


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
            # tone_judge: score=None means infra failure — treat as inconclusive
            # (not a passing guard turn; log but do not count as content failure).
            if result.score is None:
                exp_results.append(
                    {
                        "kind": exp["kind"],
                        "passed": False,
                        "skipped": False,
                        "inconclusive": True,
                        "detail": f"tone_judge_infra_failure: {result.error}",
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
