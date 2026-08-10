"""
Module: hedge_responder_probe
Layer: harness (eval tooling — imports evals/, never src/)
Purpose: Score the capability battery against a scripted always-hedge responder,
    which is EVAL-P20.2 validation (2) and the only one of its three validations a
    ratchet cannot fake.
Dependencies: stdlib argparse/pathlib/sys; pydantic; yaml; evals/ `matchers` and `summary`.
Used by: `make hedge-probe`, tests/unit/scripts/test_hedge_responder_probe.py.

Substitutes the response *after* the engine would have produced it, then runs the real
`matchers.evaluate` and the real `summary.summarize` over the result — so the number it
prints is the number a live run would print for that text, not a model of it. Wiring the
responder into the engine instead would mean adding a substitution seam to production
code for a measurement; see DEC-167 for that decision and for why the canned hedge below
is the strong adversary rather than a bland one.

"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml
from pydantic import BaseModel, ConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "evals"))

from matchers import EvalConfigError, JudgeResult, evaluate  # noqa: E402
from summary import summarize  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The scripted responder, and the reason the gate is worth anything. It asserts no fact
#: — every clause refuses to commit — but it is stocked with the battery's own surface
#: vocabulary (war, trade, trouble, harvest, heard, hard times), which is deliberate: a
#: bland "I could not say" scores 0.143 against the shipped seven and would let the gate
#: read green while changing nothing. This text reproduces the roadmap's stated baseline
#: of 6/7 = 0.857 exactly. Any capability case it passes is a case that does not test
#: capability — it can be satisfied by shrugging in the right dialect. (DEC-167)
CANNED_HEDGE: str = (
    "I have heard talk of the war and trouble on the trade roads, but whether any of it "
    "holds true I could not say. Hard times all round, and I would not want to guess at "
    "the harvest either. Ask someone who was there."
)

#: EVAL-P20.2 validation (2): the battery must hold this responder under 0.30.
HEDGE_GATE_THRESHOLD: float = 0.30

_CAPABILITY_PREFIX: str = "case_pos_"
_CASE_GLOB: str = "case_pos_*.yaml"

_DEFAULT_CASES_DIR: Path = _REPO_ROOT / "evals" / "cases"

#: Envelope fields `matchers._eval_schema` requires to be present and non-null.
#: A hedge must fail on content, never on a malformed envelope.
_NEUTRAL_ACTION: str = "idle"
_NEUTRAL_EXPRESSION: str = "neutral"

_EXIT_OK: int = 0
_EXIT_GATE_FAILED: int = 1

_UNKNOWN_KIND: str = "unknown"


class NotACapabilityCaseError(ValueError):
    """Raised when a case that is not `case_pos_*` is handed to the probe.

    The probe reports a capability rate; scoring a guard case would silently change
    what that number means.
    """


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class HedgeProbeResult(BaseModel):
    """What the always-hedge responder scored against the capability battery.

    Attributes:
        hedge: The canned response substituted for every NPC answer.
        cases: Capability cases considered.
        turns: Cases that produced a verdict (the rate's denominator).
        passes: Cases the hedge passed.
        capability_rate: `passes / turns`, or None when no case ran.
        passing_case_ids: The cases the hedge beat — the authoring work-list.
        threshold: The rate the battery must hold the hedge below.
    """

    model_config = ConfigDict(frozen=True)

    hedge: str
    cases: int
    turns: int
    passes: int
    capability_rate: float | None
    passing_case_ids: tuple[str, ...]
    threshold: float

    @property
    def meets_gate(self) -> bool:
        """True only when a rate was actually measured and it is below the threshold.

        An unmeasured battery (zero capability cases) is never a pass: "no case ran"
        and "every case held" are the same number of failures and opposite results.
        """
        if self.capability_rate is None:
            return False
        return self.capability_rate < self.threshold


# ---------------------------------------------------------------------------
# Substitution point
# ---------------------------------------------------------------------------


def synthetic_response(hedge: str) -> dict[str, Any]:
    """Build the dialogue envelope a scripted always-hedge responder would return.

    Args:
        hedge: The canned response text.
    Returns:
        A response dict shaped like the engine's, carrying `hedge` as npc_response.
    """
    return {
        "npc_response": hedge,
        "relation_deltas": [],
        "action": _NEUTRAL_ACTION,
        "facial_expression": _NEUTRAL_EXPRESSION,
    }


# ---------------------------------------------------------------------------
# Scoring — mirrors evals/runner.py::_run_case for a fixed response
# ---------------------------------------------------------------------------


def _expectation_result(expectation: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one expectation, mapping every outcome onto the runner's result shape."""
    kind = expectation.get("kind", _UNKNOWN_KIND)
    try:
        outcome = evaluate(expectation=expectation, response=response)
    except EvalConfigError as exc:
        return {"kind": kind, "passed": False, "skipped": False, "detail": f"eval_config_error: {exc}"}

    if isinstance(outcome, JudgeResult):
        if outcome.score is None:
            detail = f"judge_infra_failure: {outcome.error}"
            return {"kind": kind, "passed": False, "skipped": False, "inconclusive": True, "detail": detail}
        return {"kind": kind, "passed": bool(outcome.score), "skipped": False, "detail": outcome.error}

    passed, detail = outcome
    return {"kind": kind, "passed": passed, "skipped": False, "detail": detail}


def score_case(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Score one capability case against a fixed response.

    Args:
        case: A parsed `case_pos_*` YAML document.
        response: The response envelope to score, from `synthetic_response`.
    Returns:
        A result dict in `evals/runner.py::_run_case` shape, so `summary.summarize`
        consumes it unchanged.
    Raises:
        NotACapabilityCaseError: When the case is not a `case_pos_*` case.
    """
    case_id = str(case.get("case_id", ""))
    if not case_id.startswith(_CAPABILITY_PREFIX):
        raise NotACapabilityCaseError(
            f"'{case_id}' is not a capability case; the probe reports a capability rate "
            f"and must be given only {_CAPABILITY_PREFIX}* cases"
        )
    expectations = [_expectation_result(exp, response) for exp in case.get("expected", [])]
    return {
        "case_id": case_id,
        "description": case.get("description", ""),
        "passed": all(exp["passed"] for exp in expectations) if expectations else False,
        "expectations": expectations,
        "response": response,
    }


def probe(
    cases: Sequence[dict[str, Any]],
    *,
    hedge: str = CANNED_HEDGE,
    threshold: float = HEDGE_GATE_THRESHOLD,
) -> HedgeProbeResult:
    """Score every capability case against the always-hedge responder.

    Args:
        cases: Parsed `case_pos_*` documents.
        hedge: The canned response substituted for every NPC answer.
        threshold: The rate the battery must hold the hedge below.
    Returns:
        The measured HedgeProbeResult.
    Raises:
        NotACapabilityCaseError: When any case is not a `case_pos_*` case.
    """
    response = synthetic_response(hedge)
    results = [score_case(case, response) for case in cases]
    rolled = summarize(results)
    passing = tuple(r["case_id"] for r in results if r["passed"])
    return HedgeProbeResult(
        hedge=hedge,
        cases=rolled.capability_cases,
        turns=rolled.capability_turns,
        passes=rolled.capability_passes,
        capability_rate=rolled.capability_rate,
        passing_case_ids=passing,
        threshold=threshold,
    )


def load_capability_cases(
    cases_dir: Path,
    case_ids: Sequence[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Load every `case_pos_*.yaml` document in a directory, sorted by filename.

    Args:
        cases_dir: Directory holding eval case YAML files.
        case_ids: When given, keep only these case_ids — used to measure the
            authored subset separately from the whole battery, which is what
            EVAL-P20.2's ratchet clause scopes validation (2) to.
    Returns:
        The parsed capability cases.
    Raises:
        NotACapabilityCaseError: When `case_ids` names an id no file supplies, so a
            typo cannot quietly shrink the denominator.
    """
    loaded = tuple(
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(cases_dir.glob(_CASE_GLOB))
    )
    if case_ids is None:
        return loaded
    wanted = set(case_ids)
    kept = tuple(case for case in loaded if case.get("case_id") in wanted)
    missing = sorted(wanted - {case.get("case_id") for case in kept})
    if missing:
        raise NotACapabilityCaseError(f"no capability case found for: {', '.join(missing)}")
    return kept


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _report(result: HedgeProbeResult) -> str:
    """Render the probe result, naming every case the hedge beat."""
    rate = "N/A (no capability case ran)" if result.capability_rate is None else f"{result.capability_rate:.3f}"
    verdict = "GATE MET" if result.meets_gate else "GATE NOT MET"
    lines = [
        "always-hedge responder vs the capability battery",
        f"  hedge:      {result.hedge!r}",
        f"  capability: {result.passes}/{result.turns}  rate {rate}  (gate: < {result.threshold:.2f})",
        f"  verdict:    {verdict}",
    ]
    if result.passing_case_ids:
        lines.append("  cases the hedge passed (these do not test capability):")
        lines.extend(f"    - {case_id}" for case_id in result.passing_case_ids)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the probe over a case directory and exit non-zero when the gate is unmet."""
    parser = argparse.ArgumentParser(description="Score the capability battery against a canned hedge.")
    parser.add_argument("--cases", default=str(_DEFAULT_CASES_DIR), help="case directory (default: %(default)s)")
    parser.add_argument(
        "--case-ids", nargs="+", metavar="CASE_ID",
        help="score only these case_ids (default: the whole capability battery).",
    )
    parser.add_argument("--hedge", default=CANNED_HEDGE, help="canned response to substitute for every NPC answer")
    parser.add_argument(
        "--threshold", type=float, default=HEDGE_GATE_THRESHOLD,
        help="capability rate the battery must hold the hedge below (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    cases = load_capability_cases(Path(args.cases), args.case_ids)
    result = probe(cases, hedge=args.hedge, threshold=args.threshold)
    print(_report(result))
    return _EXIT_OK if result.meets_gate else _EXIT_GATE_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
