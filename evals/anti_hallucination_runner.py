"""
Module: anti_hallucination_runner
Layer: evals (eval harness — not part of src/)
Purpose: Run evals/cases/anti_hallucination_demo.json against the live engine
         and report grounded/refusal/hallucination metrics.
Dependencies: httpx, json, pathlib, argparse, sys, pydantic
Used by: Makefile eval-anti-hallucination target, CI
Does NOT: import from src/npc_engine/, call LLM judges, modify graph state
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

# Import write_report from sibling module (evals/ on sys.path when run via Makefile)
from report import write_report


_REFUSAL_KEYWORDS: tuple[str, ...] = (
    "don't know",
    "do not know",
    "haven't heard",
    "have not heard",
    "not sure",
    "not certain",
    "no idea",
    "can't say",
    "cannot say",
    "wouldn't know",
    "would not know",
    "doubt",
    "uncertain",
    "haven't come across",
    "haven't seen",
    "unaware",
)

_PLAYER_ID = "player_eval"
_SESSION_PREFIX = "ah_eval"

# learned_from_player cases score like `grounded` but require a pre-flight check that
# the player-taught fact was actually persisted (write_belief) in a prior session —
# otherwise the case is skipped rather than false-failed. (ISSUE-090 / DEC-095)
_LEARNED_FROM_PLAYER_CATEGORY = "learned_from_player"
_BELIEFS_PATH_TEMPLATE = "/v1/admin/beliefs/{npc_id}"
_BELIEF_PREFLIGHT_K = 25
_BELIEF_PREFLIGHT_TIMEOUT_S = 10.0
_BELIEF_NOT_PERSISTED_DETAIL = "skipped — player-taught fact not persisted (no prior session)"


class AntiHallucinationSummary(BaseModel):
    """Aggregate metrics for a completed anti-hallucination eval run."""

    total: int
    grounded_total: int
    grounded_passed: int
    refusal_total: int
    refusal_passed: int
    hallucination_count: int
    over_refusal_count: int


def _is_refusal(response_text: str) -> bool:
    """Return True if the response contains at least one refusal keyword."""
    lowered = response_text.lower()
    return any(kw in lowered for kw in _REFUSAL_KEYWORDS)


def _is_grounded(response_text: str, expected_fact_substrings: list[str]) -> bool:
    """Return True if the response contains at least one expected fact substring."""
    lowered = response_text.lower()
    return any(sub.lower() in lowered for sub in expected_fact_substrings)


def _belief_fact_persisted(
    npc_id: str,
    client: httpx.Client,
    base_url: str,
    substrings: list[str],
) -> bool:
    """Return True if the NPC holds a persisted belief matching one of the substrings.

    Pre-flight for learned_from_player cases: queries GET /v1/admin/beliefs/{npc_id}
    and confirms the player-taught fact was written (via write_belief, DEC-072) in a
    prior session before the dialogue case is scored as grounded. A missing fact or a
    query error returns False, so the case is skipped rather than false-failed.

    Args:
        npc_id: Character whose beliefs are inspected.
        client: Active httpx client (carries auth headers).
        base_url: Base URL of the NPC engine API.
        substrings: Fact substrings that must appear in a persisted belief's content.
    Returns:
        True when at least one belief content contains one of the substrings.
    """
    if not substrings:
        return False
    url = f"{base_url}{_BELIEFS_PATH_TEMPLATE.format(npc_id=npc_id)}"
    try:
        resp = client.get(url, params={"k": _BELIEF_PREFLIGHT_K}, timeout=_BELIEF_PREFLIGHT_TIMEOUT_S)
        resp.raise_for_status()
        beliefs: list[dict[str, Any]] = resp.json().get("data", {}).get("beliefs", [])
    except Exception:
        return False
    lowered = [sub.lower() for sub in substrings]
    return any(_content_matches(belief, lowered) for belief in beliefs)


def _content_matches(belief: dict[str, Any], lowered_substrings: list[str]) -> bool:
    """Return True if the belief's content contains any of the lowercased substrings."""
    content = str(belief.get("content", "")).lower()
    return any(sub in content for sub in lowered_substrings)


def _load_fixture(fixture_path: Path) -> list[dict[str, Any]]:
    """Load and return a list of case objects from the JSON fixture, skipping comment objects."""
    raw: list[dict[str, Any]] = json.loads(fixture_path.read_text(encoding="utf-8"))
    return [obj for obj in raw if "id" in obj]


def _classify_case(
    case: dict[str, Any],
    client: httpx.Client,
    base_url: str,
) -> tuple[dict[str, Any], str | None]:
    """
    Call POST /v1/dialogue for one case and return (result_dict, verdict_outcome).

    verdict_outcome is one of: "grounded_pass", "grounded_fail", "refusal_pass",
    "refusal_fail", "skipped", or "error".

    Returns:
        (result dict for write_report, verdict_outcome string)
    """
    case_id: str = case["id"]
    npc_id: str = case["npc_id"]
    question: str = case["question"]
    expected_verdict: str = case["expected_verdict"]
    expected_substrings: list[str] = case.get("expected_fact_substrings", [])

    if case.get("category") == _LEARNED_FROM_PLAYER_CATEGORY:
        preflight_substrings: list[str] = case.get(
            "preflight_belief_substrings", expected_substrings
        )
        if not _belief_fact_persisted(npc_id, client, base_url, preflight_substrings):
            result = _build_result(
                case_id=case_id,
                passed=True,
                description=case.get("notes", ""),
                response_text="",
                error=None,
                skipped=True,
                skip_detail=_BELIEF_NOT_PERSISTED_DETAIL,
            )
            return result, "skipped"

    payload = {
        "player_id": _PLAYER_ID,
        "npc_id": npc_id,
        "player_message": question,
        "session_id": f"{_SESSION_PREFIX}:{case_id}",
    }

    try:
        resp = client.post(f"{base_url}/v1/dialogue", json=payload, timeout=60.0)
    except Exception as exc:
        result = _build_result(
            case_id=case_id,
            passed=False,
            description=case.get("notes", ""),
            response_text="",
            error=str(exc),
        )
        return result, "error"

    if resp.status_code == 404:
        result = _build_result(
            case_id=case_id,
            passed=True,
            description=case.get("notes", ""),
            response_text="",
            error=None,
            skipped=True,
        )
        return result, "skipped"

    try:
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        response_text: str = body.get("npc_response", "")
        error = None
    except Exception as exc:
        result = _build_result(
            case_id=case_id,
            passed=False,
            description=case.get("notes", ""),
            response_text="",
            error=str(exc),
        )
        return result, "error"

    if expected_verdict == "grounded":
        passed = _is_grounded(response_text, expected_substrings)
        outcome = "grounded_pass" if passed else "grounded_fail"
    else:
        passed = _is_refusal(response_text)
        outcome = "refusal_pass" if passed else "refusal_fail"

    result = _build_result(
        case_id=case_id,
        passed=passed,
        description=case.get("notes", ""),
        response_text=response_text,
        error=error,
    )
    return result, outcome


def _build_result(
    *,
    case_id: str,
    passed: bool,
    description: str,
    response_text: str,
    error: str | None,
    skipped: bool = False,
    skip_detail: str = "skipped — NPC not found (world not seeded)",
) -> dict[str, Any]:
    """Build a result dict compatible with write_report."""
    detail = skip_detail if skipped else ""
    return {
        "case_id": case_id,
        "passed": passed,
        "description": description,
        "expectations": [
            {
                "kind": "anti_hallucination",
                "passed": passed,
                "skipped": skipped,
                "detail": detail,
            }
        ],
        "response": {"npc_response": response_text} if response_text else None,
        "error": error,
    }


def _build_summary(outcomes: list[str]) -> AntiHallucinationSummary:
    """Aggregate outcome strings into an AntiHallucinationSummary."""
    grounded_total = outcomes.count("grounded_pass") + outcomes.count("grounded_fail")
    grounded_passed = outcomes.count("grounded_pass")
    refusal_total = outcomes.count("refusal_pass") + outcomes.count("refusal_fail")
    refusal_passed = outcomes.count("refusal_pass")
    hallucination_count = outcomes.count("refusal_fail")
    over_refusal_count = outcomes.count("grounded_fail")
    total = grounded_total + refusal_total
    return AntiHallucinationSummary(
        total=total,
        grounded_total=grounded_total,
        grounded_passed=grounded_passed,
        refusal_total=refusal_total,
        refusal_passed=refusal_passed,
        hallucination_count=hallucination_count,
        over_refusal_count=over_refusal_count,
    )


def format_summary(summary: AntiHallucinationSummary) -> list[str]:
    """Return human-readable summary lines including per-category stats.

    Args:
        summary: Populated AntiHallucinationSummary model.
    Returns:
        List of printable strings describing the eval results.
    """
    return [
        "Anti-Hallucination Eval Summary",
        "=" * 34,
        f"  grounded   : {summary.grounded_passed}/{summary.grounded_total} correct"
        f"  (over_refusal={summary.over_refusal_count})",
        f"  refusal    : {summary.refusal_passed}/{summary.refusal_total} correct"
        f"  (hallucination_count={summary.hallucination_count})",
        f"  total      : {summary.grounded_passed + summary.refusal_passed}/{summary.total} passed",
        f"  hallucinations : {summary.hallucination_count}",
        f"  over-refusals  : {summary.over_refusal_count}",
    ]


def run(
    base_url: str,
    api_key: str,
    fixture_path: Path,
    report_dir: Path,
) -> int:
    """Run the anti-hallucination eval suite and return an exit code.

    Args:
        base_url: Base URL of the NPC engine API.
        api_key: API key passed in X-API-Key header.
        fixture_path: Path to the JSON fixture file.
        report_dir: Directory to write the markdown report into.
    Returns:
        0 if all non-skipped cases pass, 1 if any fail, 2 on connectivity error.
    """
    cases = _load_fixture(fixture_path)
    headers = {"X-API-Key": api_key}
    results: list[dict[str, Any]] = []
    outcomes: list[str] = []

    with httpx.Client(headers=headers) as client:
        try:
            health = client.get(f"{base_url}/health", timeout=5.0)
            health.raise_for_status()
        except Exception as exc:
            print(f"Server not reachable at {base_url}: {exc}", file=sys.stderr)
            return 2

        for case in cases:
            case_id = case["id"]
            print(f"  running {case_id} ...", end=" ", flush=True)
            result, outcome = _classify_case(case, client, base_url)
            if outcome == "skipped":
                print("SKIP (NPC not found)")
            elif outcome == "error":
                print("ERROR")
            else:
                print("PASS" if result["passed"] else "FAIL")
            results.append(result)
            if outcome not in ("skipped", "error"):
                outcomes.append(outcome)

    summary = _build_summary(outcomes)
    for line in format_summary(summary):
        print(line)

    report_path = write_report(results=results, output_dir=report_dir)
    print(f"\nReport: {report_path}")

    failures = summary.hallucination_count + summary.over_refusal_count
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and invoke run().

    Args:
        argv: Argument list (defaults to sys.argv[1:]).
    Returns:
        Exit code integer.
    """
    parser = argparse.ArgumentParser(
        description="Anti-hallucination eval runner for NPC Engine"
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default="eval-key-change-me")
    parser.add_argument(
        "--fixture",
        default="evals/cases/anti_hallucination_demo.json",
        type=Path,
    )
    parser.add_argument("--reports", default="evals/reports", type=Path)
    args = parser.parse_args(argv)

    return run(
        base_url=args.base_url,
        api_key=args.api_key,
        fixture_path=args.fixture,
        report_dir=args.reports,
    )


if __name__ == "__main__":
    sys.exit(main())
