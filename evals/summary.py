"""
Module: summary
Layer: evals harness (standalone — not part of the npc_engine layer model)
Purpose: Compute the published anti-hallucination headline metric and a
         categorized failure breakdown from a completed eval run's results.
Dependencies: stdlib (dataclasses), battery_rates (design-effect CI correction),
              refusal_rate (over-refusal rate display, EVAL-P20.3).
Used by: runner.py (console output), report.py (markdown summary section).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from battery_rates import BatteryRate, compute_battery_rate
import case_stats
from headline_refusal import refusal_for_battery
from null_baseline import load_null_baseline
from panel_metrics import PanelMetrics
from panel_metrics_format import console_lines, markdown_rows
from refusal_rate import RefusalRateResult, fmt_refusal_rate
import verdict_sources

# Matcher kinds tracked individually in the failure breakdown.
_KIND_SCHEMA: str = "schema"
_KIND_KEYWORD_NONE: str = "keyword_none"
_KIND_TONE_JUDGE: str = "tone_judge"
_KIND_AFFIRMS_JUDGE: str = "affirms_judge"

_SEPARATOR: str = "=" * 60

# Emitted when no guard case actually ran: the guarantee is undemonstrated, not green.
_NO_GUARD_TURNS_MESSAGE: str = "NO GUARD TURNS EVALUATED — guarantee not demonstrated"

# A run where this fraction of evaluated cases have inconclusive judge calls provides
# false confidence — the guarantee was not properly measured.
_MAX_INCONCLUSIVE_RATE: float = 0.20

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
        guard_cases: Non-skipped guard battery cases (adv + neg + ah_demo_*). A COUNT over
            both populations, which is legitimate — `check_conservation` needs the identity
            `guard_cases + capability_cases == total_cases`. There is deliberately no
            combined guard RATE beside it; see DEC-243 and `adversarial_*` /
            `anti_hallucination_*` below.
        guard_turns: Guard cases that actually ran, both populations. A count, as above.
        adversarial_cases: Non-skipped case_adv_*/case_neg_* cases.
        adversarial_turns: Adversarial cases that actually ran.
        adversarial_passes: Adversarial cases that both ran and passed.
        adversarial_rate: Pass rate over adversarial turns; None when none ran.
        adversarial_ci_low: Lower bound of the 95 % Wilson CI; None when no turns.
        adversarial_ci_high: Upper bound of the 95 % Wilson CI; None when no turns.
        adversarial_battery_rate: Full design-effect data; None when no turns.
        anti_hallucination_cases: Non-skipped ah_demo_* cases.
        anti_hallucination_turns: ah_demo_* cases that actually ran.
        anti_hallucination_passes: ah_demo_* cases that both ran and passed.
        anti_hallucination_rate: Pass rate over ah_demo_* turns; None when none ran.
        anti_hallucination_ci_low: Lower bound of the 95 % Wilson CI; None when no turns.
        anti_hallucination_ci_high: Upper bound of the 95 % Wilson CI; None when no turns.
        anti_hallucination_battery_rate: Full design-effect data; None when no turns.
        capability_cases: Non-skipped positive (case_pos_*) cases in the run.
        capability_turns: Capability cases that actually ran (non-skipped denominator).
        capability_passes: Capability cases that both ran and passed.
        capability_rate: Pass rate over capability turns; None when capability_turns == 0.
        capability_ci_low: Lower bound of the 95 % Wilson CI; None when no turns.
        capability_ci_high: Upper bound of the 95 % Wilson CI; None when no turns.
        capability_battery_rate: Full design-effect data for the capability battery; None when no turns.
        hallucination_failures: keyword_none + affirms_judge failures within guard cases.
        schema_failures: Failed schema expectations across all cases.
        keyword_none_failures: Failed keyword_none expectations across all cases.
        tone_judge_failures: Failed tone_judge expectations across all cases.
        affirms_judge_failures: Failed affirms_judge expectations across all cases.
        other_failures: Failed expectations of any other kind.
        skipped_cases: Cases where every expectation was skipped (bypass battery classification).
        excluded_cases: Non-skipped cases belonging to no published battery.
        inconclusive_failures: Judge expectations that returned score=None (infra failure).
            These are NOT counted in hallucination_failures — an Ollama timeout is not a
            content defect. An inconclusive rate above _MAX_INCONCLUSIVE_RATE marks the
            run invalid via the is_run_valid property.
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
    inconclusive_failures: int = 0
    capability_cases: int = 0
    capability_turns: int = 0
    capability_passes: int = 0
    capability_rate: float | None = None
    capability_ci_low: float | None = None
    capability_ci_high: float | None = None
    capability_battery_rate: BatteryRate | None = None
    adversarial_cases: int = 0
    adversarial_turns: int = 0
    adversarial_passes: int = 0
    adversarial_rate: float | None = None
    adversarial_ci_low: float | None = None
    adversarial_ci_high: float | None = None
    adversarial_battery_rate: BatteryRate | None = None
    anti_hallucination_cases: int = 0
    anti_hallucination_turns: int = 0
    anti_hallucination_passes: int = 0
    anti_hallucination_rate: float | None = None
    anti_hallucination_ci_low: float | None = None
    anti_hallucination_ci_high: float | None = None
    anti_hallucination_battery_rate: BatteryRate | None = None

    @property
    def guarantee_demonstrated(self) -> bool:
        """True only when at least one guard turn ran and none hallucinated.

        A run with zero evaluated guard turns proves nothing — the guarantee is
        undemonstrated, not satisfied.
        """
        return self.guard_turns > 0 and self.hallucination_failures == 0

    @property
    def is_run_valid(self) -> bool:
        """False when the inconclusive rate (inconclusive / evaluated) exceeds the threshold.

        A run where too many judge calls timed out provides false confidence: the
        guarantee rate is understated and the run must be flagged as invalid rather
        than quietly optimistic.
        """
        if self.evaluated_cases == 0:
            return True
        return (self.inconclusive_failures / self.evaluated_cases) < _MAX_INCONCLUSIVE_RATE

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

    # The guard battery is scored as TWO populations and never as one (DEC-243). The
    # counts below still span both, because `check_conservation`'s identity is about
    # cases; only the RATES are kept apart.
    adv_results = [
        r for r in guard_results
        if case_stats.guard_population(r.get("case_id", "")) == "adversarial"
    ]
    ah_results = [
        r for r in guard_results
        if case_stats.guard_population(r.get("case_id", "")) == "anti_hallucination"
    ]

    g_br = compute_battery_rate(guard_results)
    adv_br = compute_battery_rate(adv_results)
    ah_br = compute_battery_rate(ah_results)
    c_br = compute_battery_rate(cap_results)

    tally = _tally_failures(results)

    return EvalSummary(
        total_cases=total_cases,
        evaluated_cases=evaluated_cases,
        total_turns=evaluated_cases,
        guard_cases=g_br.n_cases if g_br else 0,
        excluded_cases=len(excluded_results),
        guard_turns=g_br.n_records if g_br else 0,
        hallucination_failures=tally["hallucination"],
        schema_failures=tally["schema"],
        keyword_none_failures=tally["keyword_none"],
        tone_judge_failures=tally["tone_judge"],
        affirms_judge_failures=tally["affirms_judge"],
        other_failures=tally["other"],
        inconclusive_failures=tally["inconclusive"],
        skipped_cases=skipped_count,
        capability_cases=c_br.n_cases if c_br else 0,
        capability_turns=c_br.n_records if c_br else 0,
        capability_passes=c_br.passes if c_br else 0,
        capability_rate=c_br.pass_rate if c_br else None,
        capability_ci_low=c_br.ci_low if c_br else None,
        capability_ci_high=c_br.ci_high if c_br else None,
        capability_battery_rate=c_br,
        adversarial_cases=adv_br.n_cases if adv_br else 0,
        adversarial_turns=adv_br.n_records if adv_br else 0,
        adversarial_passes=adv_br.passes if adv_br else 0,
        adversarial_rate=adv_br.pass_rate if adv_br else None,
        adversarial_ci_low=adv_br.ci_low if adv_br else None,
        adversarial_ci_high=adv_br.ci_high if adv_br else None,
        adversarial_battery_rate=adv_br,
        anti_hallucination_cases=ah_br.n_cases if ah_br else 0,
        anti_hallucination_turns=ah_br.n_records if ah_br else 0,
        anti_hallucination_passes=ah_br.passes if ah_br else 0,
        anti_hallucination_rate=ah_br.pass_rate if ah_br else None,
        anti_hallucination_ci_low=ah_br.ci_low if ah_br else None,
        anti_hallucination_ci_high=ah_br.ci_high if ah_br else None,
        anti_hallucination_battery_rate=ah_br,
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


def _bucket_expectation(exp: dict, is_guard: bool, tally: dict[str, int]) -> None:
    """Update tally in-place for one failed expectation.

    Inconclusive expectations (judge infra failure) go to the 'inconclusive' bucket
    and are excluded from all content-failure counts, including 'hallucination'.
    """
    if exp.get("inconclusive"):
        tally["inconclusive"] += 1
        return
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


def _tally_failures(results: list[dict]) -> dict[str, int]:
    """Bucket failing expectations by matcher kind and lore-hallucination scope.

    Both keyword_none and affirms_judge failures inside a guard case count as
    lore hallucinations. Inconclusive expectations (judge unavailable) are tallied
    separately and excluded from all content failure counts.
    Cases with no failed expectations are skipped without consulting classify_battery,
    so fully-skipped cases never trigger a ValueError for unclassifiable IDs.
    """
    tally = {
        "schema": 0, "keyword_none": 0, "tone_judge": 0,
        "affirms_judge": 0, "other": 0, "hallucination": 0, "inconclusive": 0,
    }
    for result in results:
        failed = _failed_expectations(result)
        if not failed:
            continue
        battery = case_stats.classify_battery(result.get("case_id", ""))
        is_guard = battery == "guard"
        for exp in failed:
            _bucket_expectation(exp, is_guard, tally)
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
        f"    inconclusive (judge unavailable): {s.inconclusive_failures}",
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
        f"| inconclusive (judge unavailable) | {s.inconclusive_failures} |",
    ]


def _format_battery_counts_lines(s: EvalSummary) -> list[str]:
    """Build the per-battery case/turn count lines for the console summary."""
    return [
        f"  Guard - adversarial (case_adv_* + case_neg_*): {s.adversarial_cases} cases, "
        f"{s.adversarial_turns} turns evaluated",
        f"  Guard - anti-hallucination (ah_demo_*): {s.anti_hallucination_cases} cases, "
        f"{s.anti_hallucination_turns} turns evaluated",
        f"  Capability battery (case_pos_*): {s.capability_cases} cases, "
        f"{s.capability_turns} turns evaluated",
        f"  Excluded (not in any battery): {s.excluded_cases} cases",
        f"  All cases: {s.evaluated_cases} evaluated / {s.total_cases} total "
        f"({s.skipped_cases} skipped)",
    ]


def _format_validity_warning(s: EvalSummary) -> list[str]:
    """Return an [INVALID RUN] warning line when the inconclusive rate exceeds the threshold."""
    if s.is_run_valid:
        return []
    return [
        f"  [INVALID RUN] inconclusive rate too high: "
        f"{s.inconclusive_failures}/{s.evaluated_cases} judge calls timed out"
    ]


def _assert_paired_rates(s: EvalSummary) -> None:
    """Raise ValueError when guard rates and the capability rate are not both present.

    The headline must always quote the rates together so readers cannot see a guard
    number without its capability counterpart, and vice-versa.

    Since DEC-243 "the guard rate" is two rates, and either population having data makes
    the guard side present. The pairing rule is unchanged; only what counts as the guard
    side is, because there is no longer a combined guard rate to test.

    Args:
        s: The EvalSummary to validate.
    Raises:
        ValueError: When only one of the two paired sides has evaluated data.
    """
    guard_has_data = s.adversarial_rate is not None or s.anti_hallucination_rate is not None
    cap_has_data = s.capability_rate is not None
    if guard_has_data and not cap_has_data:
        raise ValueError(_UNPAIRED_GUARD_ONLY)
    if cap_has_data and not guard_has_data:
        raise ValueError(_UNPAIRED_CAPABILITY_ONLY)


def _format_refusal_rate_line(refusal_result: RefusalRateResult | None) -> list[str]:
    """Build the over-refusal rate console line, or [] when no result was supplied.

    Kept separate from the guard/capability rates because over-refusal is scored
    over grounded responses independently of the guard/capability battery split —
    see refusal_rate.score_refusal_rate.
    """
    if refusal_result is None:
        return []
    return [f"    Over-refusal rate: {fmt_refusal_rate(refusal_result)}"]


def _format_refusal_rate_row(refusal_result: RefusalRateResult | None) -> list[str]:
    """Build the over-refusal rate markdown table row, or [] when no result was supplied."""
    if refusal_result is None:
        return []
    return [f"| Over-refusal (grounded, excludes infra failures) | {fmt_refusal_rate(refusal_result)} |"]


def _gated_rate_strs(
    summary: EvalSummary,
    baseline: dict[str, dict] | None,
) -> tuple[str, str, str]:
    """The three battery rate strings, each refused where engine <= null (R2.5 step 3c).

    Applied strictly per population — adversarial, anti-hallucination and capability
    are compared to their own recorded null and never to each other's, because
    combining populations is the error DEC-243 removed.

    Args:
        summary: The run being rendered.
        baseline: {battery: entry} from null_baseline.load_null_baseline; None loads
            the recorded artifact. Pass {} to render rates ungated.
    Returns:
        (adversarial, anti_hallucination, capability) display strings.
    """
    marks = load_null_baseline() if baseline is None else baseline
    adv = _pick_rate_str(
        summary.adversarial_battery_rate,
        summary.adversarial_passes, summary.adversarial_turns,
        summary.adversarial_rate, summary.adversarial_ci_low, summary.adversarial_ci_high,
    )
    ah = _pick_rate_str(
        summary.anti_hallucination_battery_rate,
        summary.anti_hallucination_passes, summary.anti_hallucination_turns,
        summary.anti_hallucination_rate, summary.anti_hallucination_ci_low,
        summary.anti_hallucination_ci_high,
    )
    cap = _pick_rate_str(
        summary.capability_battery_rate,
        summary.capability_passes, summary.capability_turns,
        summary.capability_rate, summary.capability_ci_low, summary.capability_ci_high,
    )
    return (
        refusal_for_battery("adversarial", summary.adversarial_rate, marks) or adv,
        refusal_for_battery("anti_hallucination", summary.anti_hallucination_rate, marks) or ah,
        refusal_for_battery("capability", summary.capability_rate, marks) or cap,
    )


def format_summary_lines(
    summary: EvalSummary,
    *,
    refusal_result: RefusalRateResult | None = None,
    panel_metrics: PanelMetrics | None = None,
    null_baseline: dict[str, dict] | None = None,
) -> list[str]:
    """Render as plain-text console lines; guard and capability rates adjacent.

    Args:
        summary: The EvalSummary to render.
        refusal_result: Optional over-refusal rate (evals/refusal_rate.py); when
            supplied, an "Over-refusal rate" line is printed next to the guard and
            capability rates. Omitted entirely when None — over-refusal scoring is
            a separate, optional measurement, not every caller runs it.
        panel_metrics: Optional panel agreement statistics
            (evals/panel_metrics.py, EVAL-P21.2); when supplied, the Fleiss-kappa
            headline, raw pairwise agreement, the per-criterion breakdown and the
            repeat-flip decomposition are printed. Omitted when None — single-judge
            runs have no panel to agree within.
    Raises:
        ValueError: When the guard rates and the capability rate are not paired.
    """
    _assert_paired_rates(summary)
    adv_rate_str, ah_rate_str, c_rate_str = _gated_rate_strs(summary, null_baseline)
    return [
        _SEPARATOR,
        "ANTI-HALLUCINATION GUARANTEE",
        _SEPARATOR,
        f"  {summary.headline}",
        "",
        "  Rates (k/n  rate  95% CI) — the two guard populations never combine (DEC-243):",
        f"    Guard, adversarial:        {adv_rate_str}",
        f"    Guard, anti-hallucination: {ah_rate_str}",
        f"    Capability rate:           {c_rate_str}",
        *_format_refusal_rate_line(refusal_result),
        *console_lines(panel_metrics),
        "",
        *_format_battery_counts_lines(summary),
        "",
        *_format_failure_breakdown_lines(summary),
        *_format_validity_warning(summary),
        _SEPARATOR,
    ]


def format_summary_markdown(
    summary: EvalSummary,
    *,
    refusal_result: RefusalRateResult | None = None,
    panel_metrics: PanelMetrics | None = None,
    null_baseline: dict[str, dict] | None = None,
) -> list[str]:
    """Render as markdown lines for the report; guard and capability rates adjacent.

    Args:
        summary: The EvalSummary to render.
        refusal_result: Optional over-refusal rate; when supplied, adds a row to
            the rate table. See format_summary_lines for why this is optional.
        panel_metrics: Optional panel agreement statistics; when supplied, adds rows.
            See format_summary_lines for why this is optional.
    Raises:
        ValueError: When the guard rates and the capability rate are not paired.
    """
    _assert_paired_rates(summary)
    adv_rate_str, ah_rate_str, c_rate_str = _gated_rate_strs(summary, null_baseline)
    return [
        "## Anti-Hallucination Guarantee",
        "",
        f"**{summary.headline}**",
        "",
        "| Battery | k/n | Rate · 95% CI |",
        "|---|---|---|",
        f"| Guard - adversarial (case_adv_* + case_neg_*) | "
        f"{summary.adversarial_passes}/{summary.adversarial_turns} | {adv_rate_str} |",
        f"| Guard - anti-hallucination (ah_demo_*) | "
        f"{summary.anti_hallucination_passes}/{summary.anti_hallucination_turns} | {ah_rate_str} |",
        f"| Capability (case_pos_*) | {summary.capability_passes}/{summary.capability_turns} | {c_rate_str} |",
        *_format_refusal_rate_row(refusal_result),
        *markdown_rows(panel_metrics),
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
