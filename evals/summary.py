"""
Module: summary
Layer: eval harness (standalone — not part of the npc_engine layer model)
Purpose: Compute the published anti-hallucination headline metric and a
         categorized failure breakdown from a completed eval run's results.
Dependencies: stdlib only (dataclasses).
Used by: runner.py (console output), report.py (markdown summary section).
"""

from __future__ import annotations

from dataclasses import dataclass

# Guard battery = the cases that prove "NPCs never invent lore or break character".
# Adversarial cases (case_adv_*) and negative knowledge-guard cases (case_neg_*).
_GUARD_PREFIXES: tuple[str, ...] = ("case_adv_", "case_neg_")

# Matcher kinds tracked individually in the failure breakdown.
_KIND_SCHEMA: str = "schema"
_KIND_KEYWORD_NONE: str = "keyword_none"
_KIND_TONE_JUDGE: str = "tone_judge"

_SEPARATOR: str = "=" * 60

# Emitted when no guard case actually ran: the guarantee is undemonstrated, not green.
_NO_GUARD_TURNS_MESSAGE: str = "NO GUARD TURNS EVALUATED — guarantee not demonstrated"


@dataclass(frozen=True)
class EvalSummary:
    """Immutable roll-up of a single eval run, with the headline guarantee.

    Attributes:
        total_cases: Number of eval cases in the run.
        total_turns: Cases that actually invoked the NPC (not fully skipped).
        guard_cases: Adversarial + negative cases (the anti-hallucination battery).
        guard_turns: Guard cases that actually ran (denominator of the headline).
        hallucination_failures: keyword_none failures within guard cases.
        schema_failures: Failed schema expectations across all cases.
        keyword_none_failures: Failed keyword_none expectations across all cases.
        tone_judge_failures: Failed tone_judge expectations across all cases.
        other_failures: Failed expectations of any other kind.
        skipped_cases: Cases where every expectation was skipped.
    """

    total_cases: int
    total_turns: int
    guard_cases: int
    guard_turns: int
    hallucination_failures: int
    schema_failures: int
    keyword_none_failures: int
    tone_judge_failures: int
    other_failures: int
    skipped_cases: int

    @property
    def guarantee_demonstrated(self) -> bool:
        """True only when at least one guard turn ran and none hallucinated.

        A run with zero evaluated guard turns proves nothing — the guarantee is
        undemonstrated, not satisfied.
        """
        return self.guard_turns > 0 and self.hallucination_failures == 0

    @property
    def headline(self) -> str:
        """The published guarantee string, e.g. '0 lore hallucinations across 17 adversarial turns'.

        When no guard turn ran, returns an explicit not-demonstrated notice so the
        headline can never read green vacuously.
        """
        if self.guard_turns == 0:
            return _NO_GUARD_TURNS_MESSAGE
        plural = "" if self.hallucination_failures == 1 else "s"
        return (
            f"{self.hallucination_failures} lore hallucination{plural} "
            f"across {self.guard_turns} adversarial turns"
        )


def _is_skipped_case(result: dict) -> bool:
    """A case is skipped when it has no expectations or all of them are skipped."""
    expectations = result.get("expectations", [])
    if not expectations:
        return True
    return all(exp.get("skipped") for exp in expectations)


def _is_guard_case(case_id: str) -> bool:
    """True if the case belongs to the adversarial/negative anti-hallucination battery."""
    return case_id.startswith(_GUARD_PREFIXES)


def _failed_expectations(result: dict) -> list[dict]:
    """Return non-skipped, failing expectations for a case."""
    return [
        exp
        for exp in result.get("expectations", [])
        if not exp.get("skipped") and not exp.get("passed")
    ]


def summarize(results: list[dict]) -> EvalSummary:
    """Compute the headline metric and failure breakdown for an eval run.

    Args:
        results: Per-case result dicts as produced by runner._run_case
                 (keys: case_id, expectations, ...).
    Returns:
        An EvalSummary capturing the guarantee number and failure tallies.
    """
    total_cases = len(results)
    skipped_cases = sum(1 for result in results if _is_skipped_case(result))

    guard_results = [r for r in results if _is_guard_case(r.get("case_id", ""))]
    guard_turns = sum(1 for r in guard_results if not _is_skipped_case(r))

    tally = _tally_failures(results)

    return EvalSummary(
        total_cases=total_cases,
        total_turns=total_cases - skipped_cases,
        guard_cases=len(guard_results),
        guard_turns=guard_turns,
        hallucination_failures=tally["hallucination"],
        schema_failures=tally["schema"],
        keyword_none_failures=tally["keyword_none"],
        tone_judge_failures=tally["tone_judge"],
        other_failures=tally["other"],
        skipped_cases=skipped_cases,
    )


def _tally_failures(results: list[dict]) -> dict[str, int]:
    """Bucket failing expectations by matcher kind and lore-hallucination scope."""
    tally = {"schema": 0, "keyword_none": 0, "tone_judge": 0, "other": 0, "hallucination": 0}
    for result in results:
        is_guard = _is_guard_case(result.get("case_id", ""))
        for exp in _failed_expectations(result):
            kind = exp.get("kind", "")
            if kind == _KIND_SCHEMA:
                tally["schema"] += 1
            elif kind == _KIND_KEYWORD_NONE:
                tally["keyword_none"] += 1
                if is_guard:
                    tally["hallucination"] += 1
            elif kind == _KIND_TONE_JUDGE:
                tally["tone_judge"] += 1
            else:
                tally["other"] += 1
    return tally


def format_summary_lines(summary: EvalSummary) -> list[str]:
    """Render the summary as plain-text console lines."""
    return [
        _SEPARATOR,
        "ANTI-HALLUCINATION GUARANTEE",
        _SEPARATOR,
        f"  {summary.headline}",
        "",
        f"  Guard battery (adversarial + negative): {summary.guard_cases} cases, "
        f"{summary.guard_turns} turns evaluated",
        f"  All cases: {summary.total_cases} ({summary.total_turns} turns, "
        f"{summary.skipped_cases} skipped)",
        "",
        "  Failure breakdown:",
        f"    schema failures:       {summary.schema_failures}",
        f"    keyword_none failures: {summary.keyword_none_failures}",
        f"    tone_judge failures:   {summary.tone_judge_failures}",
        f"    other failures:        {summary.other_failures}",
        _SEPARATOR,
    ]


def format_summary_markdown(summary: EvalSummary) -> list[str]:
    """Render the summary as markdown lines for the top of the eval report."""
    return [
        "## Anti-Hallucination Guarantee",
        "",
        f"**{summary.headline}**",
        "",
        f"- Guard battery (adversarial + negative): **{summary.guard_cases}** cases, "
        f"**{summary.guard_turns}** turns evaluated",
        f"- All cases: {summary.total_cases} ({summary.total_turns} turns, "
        f"{summary.skipped_cases} skipped)",
        "",
        "| Failure kind | Count |",
        "|---|---|",
        f"| schema | {summary.schema_failures} |",
        f"| keyword_none | {summary.keyword_none_failures} |",
        f"| tone_judge | {summary.tone_judge_failures} |",
        f"| other | {summary.other_failures} |",
        "",
        "---",
        "",
    ]
