"""
Module: summary
Layer: eval harness (standalone — not part of the npc_engine layer model)
Purpose: Compute the published anti-hallucination headline metric and a
         categorized failure breakdown from a completed eval run's results.
Dependencies: stdlib (dataclasses), battery_rates (design-effect CI correction).
Used by: runner.py (console output), report.py (markdown summary section).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from battery_rates import BatteryRate, compute_battery_rate
import case_stats
import verdict_sources

# Matcher kinds tracked individually in the failure breakdown.
_KIND_SCHEMA: str = "schema"
_KIND_KEYWORD_NONE: str = "keyword_none"
_KIND_TONE_JUDGE: str = "tone_judge"
_KIND_AFFIRMS_JUDGE: str = "affirms_judge"

_SEPARATOR: str = "=" * 60

# Emitted when no guard case actually ran: the guarantee is undemonstrated, not green.
_NO_GUARD_TURNS_MESSAGE: str = "NO GUARD TURNS EVALUATED — guarantee not demonstrated"

# Raised when exactly one of the paired rates is present (guard without capability or vice-versa).
_UNPAIRED_GUARD_ONLY: str = (
    "capability rate is required alongside the guard rate; "
    "cannot render an unpaired headline"
)
_UNPAIRED_CAPABILITY_ONLY: str = (
    "guard rate is required alongside the capability rate; "
    "cannot render an unpaired headline"
)


@dataclass(frozen=True)
class EvalSummary:
    """Immutable roll-up of a single eval run, with the headline guarantee.

    Attributes:
        total_cases: Number of eval cases in the run.
        evaluated_cases: Non-skipped cases (guard + capability + excluded).
        total_turns: Cases that actually invoked the NPC (equals evaluated_cases).
        guard_cases: Non-skipped guard battery cases (adv + neg + ah_demo_*).
        guard_turns: Guard cases that actually ran (denominator of the headline).
        guard_passes: Guard cases that both ran and passed.
        guard_rate: Pass rate over guard turns; None when guard_turns == 0.
        guard_ci_low: Lower bound of the 95 % Wilson CI for guard_rate; None when no turns.
        guard_ci_high: Upper bound of the 95 % Wilson CI for guard_rate; None when no turns.
        capability_cases: Non-skipped positive (case_pos_*) cases in the run.
        capability_turns: Capability cases that actually ran (non-skipped denominator).
        capability_passes: Capability cases that both ran and passed.
        capability_rate: Pass rate over capability turns; None when capability_turns == 0.
        capability_ci_low: Lower bound of the 95 % Wilson CI; None when no turns.
        capability_ci_high: Upper bound of the 95 % Wilson CI; None when no turns.
        guard_battery_rate: Full design-effect data for the guard battery; None when no turns.
        capability_battery_rate: Full design-effect data for the capability battery; None when no turns.
        hallucination_failures: keyword_none + affirms_judge failures within guard cases.
        schema_failures: Failed schema expectations across all cases.
        keyword_none_failures: Failed keyword_none expectations across all cases.
        tone_judge_failures: Failed tone_judge expectations across all cases.
        affirms_judge_failures: Failed affirms_judge expectations across all cases.
        other_failures: Failed expectations of any other kind.
        skipped_cases: Cases where every expectation was skipped (bypass battery classification).
        excluded_cases: Non-skipped cases belonging to no published battery.
    """

    total_cases: int
    evaluated_cases: int
    total_turns: int
    guard_cases: int
    guard_turns: int
    hallucination_failures: int
    schema_failures: int
    keyword_none_failures: int
    tone_judge_failures: int
    affirms_judge_failures: int
    other_failures: int
    skipped_cases: int
    excluded_cases: int = 0
    guard_passes: int = 0
    guard_rate: float | None = None
    guard_ci_low: float | None = None
    guard_ci_high: float | None = None
    capability_cases: int = 0
    capability_turns: int = 0
    capability_passes: int = 0
    capability_rate: float | None = None
    capability_ci_low: float | None = None
    capability_ci_high: float | None = None
    guard_battery_rate: BatteryRate | None = None
    capability_battery_rate: BatteryRate | None = None

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


def _failed_expectations(result: dict) -> list[dict]:
    """Return non-skipped, failing expectations for a case."""
    return [
        exp
        for exp in result.get("expectations", [])
        if not exp.get("skipped") and not exp.get("passed")
    ]


def summarize(results: list[dict]) -> EvalSummary:
    """Compute the headline metric and failure breakdown for an eval run.

    Skipped cases bypass battery classification (they have no expectations to evaluate).
    Non-skipped cases are classified via case_stats.classify_battery, which raises
    ValueError for any case_id matching no known prefix.

    Args:
        results: Per-case result dicts as produced by runner._run_case
                 (keys: case_id, expectations, ...).
    Returns:
        An EvalSummary capturing the guarantee number and failure tallies.
    Raises:
        ValueError: When any non-skipped case_id matches no known battery prefix.
    """
    total_cases = len(results)

    guard_results: list[dict] = []
    cap_results: list[dict] = []
    excluded_results: list[dict] = []
    skipped_count = 0

    for r in results:
        if _is_skipped_case(r):
            skipped_count += 1
            continue
        battery = case_stats.classify_battery(r.get("case_id", ""))
        if battery == "guard":
            guard_results.append(r)
        elif battery == "capability":
            cap_results.append(r)
        else:
            excluded_results.append(r)

    evaluated_cases = len(guard_results) + len(cap_results) + len(excluded_results)

    g_br = compute_battery_rate(guard_results)
    c_br = compute_battery_rate(cap_results)

    tally = _tally_failures(results)

    return EvalSummary(
        total_cases=total_cases,
        evaluated_cases=evaluated_cases,
        total_turns=evaluated_cases,
        guard_cases=len(guard_results),
        excluded_cases=len(excluded_results),
        guard_turns=g_br.n_records if g_br else 0,
        hallucination_failures=tally["hallucination"],
        schema_failures=tally["schema"],
        keyword_none_failures=tally["keyword_none"],
        tone_judge_failures=tally["tone_judge"],
        affirms_judge_failures=tally["affirms_judge"],
        other_failures=tally["other"],
        skipped_cases=skipped_count,
        guard_passes=g_br.passes if g_br else 0,
        guard_rate=g_br.pass_rate if g_br else None,
        guard_ci_low=g_br.ci_low if g_br else None,
        guard_ci_high=g_br.ci_high if g_br else None,
        capability_cases=len(cap_results),
        capability_turns=c_br.n_records if c_br else 0,
        capability_passes=c_br.passes if c_br else 0,
        capability_rate=c_br.pass_rate if c_br else None,
        capability_ci_low=c_br.ci_low if c_br else None,
        capability_ci_high=c_br.ci_high if c_br else None,
        guard_battery_rate=g_br,
        capability_battery_rate=c_br,
    )


def summarize_from_dir(gen_dir: Path) -> EvalSummary:
    """Load verdicts from gen_dir (both sources) and return a summary.

    Reads judged.jsonl and deterministic_judged.jsonl from gen_dir, merges them
    via verdict_sources.load_unified_rows, and feeds the unified per-case results
    into summarize() so capability and guard turns from deterministic-only cases
    (those with no LLM judge expectations) are included in the headline metric.

    Args:
        gen_dir: Generation directory produced by a judge/deterministic-verdicts pass.
    Returns:
        EvalSummary aggregated across both verdict sources.
    Raises:
        ValueError: If either verdict file contains malformed rows.
    """
    rows = verdict_sources.load_unified_rows(gen_dir)
    results = verdict_sources.to_summarize_results(rows)
    return summarize(results)


def _tally_failures(results: list[dict]) -> dict[str, int]:
    """Bucket failing expectations by matcher kind and lore-hallucination scope.

    Both keyword_none and affirms_judge failures inside a guard case count as
    lore hallucinations, so the headline metric reflects every caught false-claim
    affirmation — not just literal forbidden-substring hits.
    Cases with no failed expectations are skipped without consulting classify_battery,
    so fully-skipped cases never trigger a ValueError for unclassifiable IDs.
    """
    tally = {
        "schema": 0,
        "keyword_none": 0,
        "tone_judge": 0,
        "affirms_judge": 0,
        "other": 0,
        "hallucination": 0,
    }
    for result in results:
        failed = _failed_expectations(result)
        if not failed:
            continue
        battery = case_stats.classify_battery(result.get("case_id", ""))
        is_guard = battery == "guard"
        for exp in failed:
            kind = exp.get("kind", "")
            if kind == _KIND_SCHEMA:
                tally["schema"] += 1
            elif kind == _KIND_KEYWORD_NONE:
                tally["keyword_none"] += 1
                if is_guard:
                    tally["hallucination"] += 1
            elif kind == _KIND_TONE_JUDGE:
                tally["tone_judge"] += 1
            elif kind == _KIND_AFFIRMS_JUDGE:
                tally["affirms_judge"] += 1
                if is_guard:
                    tally["hallucination"] += 1
            else:
                tally["other"] += 1
    return tally


def _fmt_rate(k: int, n: int, rate: float | None, ci_low: float | None, ci_high: float | None) -> str:
    """Format k/n, rate, and Wilson CI as a compact string, or 'N/A' when not computed.

    Args:
        k: Number of passes.
        n: Number of evaluated turns (denominator).
        rate: Pass rate, or None when n == 0.
        ci_low: Lower bound of the 95 % Wilson CI, or None when n == 0.
        ci_high: Upper bound of the 95 % Wilson CI, or None when n == 0.
    Returns:
        Formatted string including k/n, rate, and interval, or 'N/A' when no turns ran.
    """
    if rate is None:
        return "N/A (no evaluated turns)"
    return f"{k}/{n}  {rate:.3f}  95% CI [{ci_low:.3f}–{ci_high:.3f}]"


def _fmt_battery_rate(br: BatteryRate) -> str:
    """Format a BatteryRate including design-effect metadata and corrected CI.

    Args:
        br: Rao-Scott corrected battery rate.
    Returns:
        'passes/records (n_cases=N, k=K, n_eff=E, rho=R)  rate  95% CI [lo–hi]'
    """
    return (
        f"{br.format_summary()}  {br.pass_rate:.3f}  "
        f"95% CI [{br.ci_low:.4f}–{br.ci_high:.4f}]"
    )


def _pick_rate_str(
    battery_rate: BatteryRate | None,
    passes: int,
    turns: int,
    rate: float | None,
    ci_low: float | None,
    ci_high: float | None,
) -> str:
    """Return the design-effect rate string when available, else plain Wilson format."""
    if battery_rate is not None:
        return _fmt_battery_rate(battery_rate)
    return _fmt_rate(passes, turns, rate, ci_low, ci_high)


def _format_failure_breakdown_lines(s: EvalSummary) -> list[str]:
    """Build the failure breakdown section for the console summary."""
    return [
        "  Failure breakdown:",
        f"    schema failures:        {s.schema_failures}",
        f"    keyword_none failures:  {s.keyword_none_failures}",
        f"    tone_judge failures:    {s.tone_judge_failures}",
        f"    affirms_judge failures: {s.affirms_judge_failures}",
        f"    other failures:         {s.other_failures}",
    ]


def _format_failure_breakdown_md(s: EvalSummary) -> list[str]:
    """Build the failure kind table rows for the markdown report."""
    return [
        "| Failure kind | Count |",
        "|---|---|",
        f"| schema | {s.schema_failures} |",
        f"| keyword_none | {s.keyword_none_failures} |",
        f"| tone_judge | {s.tone_judge_failures} |",
        f"| affirms_judge | {s.affirms_judge_failures} |",
        f"| other | {s.other_failures} |",
    ]


def _assert_paired_rates(s: EvalSummary) -> None:
    """Raise ValueError when exactly one of guard_rate / capability_rate is not None.

    The headline must always quote both rates together so readers cannot see the
    guard number without its capability counterpart, and vice-versa.

    Args:
        s: The EvalSummary to validate.
    Raises:
        ValueError: When only one of the two paired rates has evaluated data.
    """
    guard_has_data = s.guard_rate is not None
    cap_has_data = s.capability_rate is not None
    if guard_has_data and not cap_has_data:
        raise ValueError(_UNPAIRED_GUARD_ONLY)
    if cap_has_data and not guard_has_data:
        raise ValueError(_UNPAIRED_CAPABILITY_ONLY)


def format_summary_lines(summary: EvalSummary) -> list[str]:
    """Render as plain-text console lines; guard and capability rates adjacent.

    Raises:
        ValueError: When only one of guard_rate / capability_rate is present.
    """
    _assert_paired_rates(summary)
    g_rate_str = _pick_rate_str(
        summary.guard_battery_rate,
        summary.guard_passes, summary.guard_turns,
        summary.guard_rate, summary.guard_ci_low, summary.guard_ci_high,
    )
    c_rate_str = _pick_rate_str(
        summary.capability_battery_rate,
        summary.capability_passes, summary.capability_turns,
        summary.capability_rate, summary.capability_ci_low, summary.capability_ci_high,
    )
    return [
        _SEPARATOR,
        "ANTI-HALLUCINATION GUARANTEE",
        _SEPARATOR,
        f"  {summary.headline}",
        "",
        "  Rates (guard vs capability — k/n  rate  95% CI):",
        f"    Guard rate:       {g_rate_str}",
        f"    Capability rate:  {c_rate_str}",
        "",
        f"  Guard battery (adv + neg + ah_demo_*): {summary.guard_cases} cases, "
        f"{summary.guard_turns} turns evaluated",
        f"  Capability battery (case_pos_*): {summary.capability_cases} cases, "
        f"{summary.capability_turns} turns evaluated",
        f"  Excluded (not in any battery): {summary.excluded_cases} cases",
        f"  All cases: {summary.evaluated_cases} evaluated / {summary.total_cases} total "
        f"({summary.skipped_cases} skipped)",
        "",
        *_format_failure_breakdown_lines(summary),
        _SEPARATOR,
    ]


def format_summary_markdown(summary: EvalSummary) -> list[str]:
    """Render as markdown lines for the report; guard and capability rates adjacent.

    Raises:
        ValueError: When only one of guard_rate / capability_rate is present.
    """
    _assert_paired_rates(summary)
    g_rate_str = _pick_rate_str(
        summary.guard_battery_rate,
        summary.guard_passes, summary.guard_turns,
        summary.guard_rate, summary.guard_ci_low, summary.guard_ci_high,
    )
    c_rate_str = _pick_rate_str(
        summary.capability_battery_rate,
        summary.capability_passes, summary.capability_turns,
        summary.capability_rate, summary.capability_ci_low, summary.capability_ci_high,
    )
    return [
        "## Anti-Hallucination Guarantee",
        "",
        f"**{summary.headline}**",
        "",
        "| Battery | k/n | Rate · 95% CI |",
        "|---|---|---|",
        f"| Guard (adv + neg + ah_demo_*) | {summary.guard_passes}/{summary.guard_turns} | {g_rate_str} |",
        f"| Capability (case_pos_*) | {summary.capability_passes}/{summary.capability_turns} | {c_rate_str} |",
        "",
        f"All cases: {summary.evaluated_cases} evaluated / {summary.total_cases} total "
        f"({summary.guard_cases} guard, {summary.capability_cases} capability, "
        f"{summary.excluded_cases} excluded, {summary.skipped_cases} skipped)",
        "",
        *_format_failure_breakdown_md(summary),
        "",
        "---",
        "",
    ]
