"""
Module: panel_metrics_format
Layer: evals (eval harness — not part of src/)
Purpose: Render PanelMetrics as console lines and markdown table rows. Kept out
         of summary.py, which is already over the 300-line cap and whose job is
         the run summary, not panel statistics.
Dependencies: typing; panel_metrics (PanelMetrics, KappaResult, ...)
Used by: summary.py (format_summary_lines / format_summary_markdown)
Does NOT: compute statistics — panel_metrics owns that.
"""

from __future__ import annotations

from panel_metrics import KappaResult, PanelMetrics

# Landis & Koch (1977) descriptive bands, printed beside kappa so the number is
# not read as if it were a percentage. Ordered high to low; first match wins.
_KAPPA_BANDS: tuple[tuple[float, str], ...] = (
    (0.81, "almost perfect"),
    (0.61, "substantial"),
    (0.41, "moderate"),
    (0.21, "fair"),
    (0.01, "slight"),
)
_KAPPA_BAND_FLOOR: str = "poor"


def kappa_band(kappa: float) -> str:
    """Return the Landis-Koch descriptive band for a kappa value."""
    for threshold, label in _KAPPA_BANDS:
        if kappa >= threshold:
            return label
    return _KAPPA_BAND_FLOOR


def _fmt_kappa(result: KappaResult) -> str:
    """Format kappa with its CI, band and n — or say why it is undefined."""
    if result.kappa is None:
        return f"undefined ({result.undefined_reason}), n={result.n_items}"
    ci = ""
    if result.ci_low is not None and result.ci_high is not None:
        ci = f" 95% CI [{result.ci_low:.3f}-{result.ci_high:.3f}]"
    return f"{result.kappa:.3f} ({kappa_band(result.kappa)}){ci}  n={result.n_items}"


def _fmt_raw(metrics: PanelMetrics) -> str:
    """Format raw pairwise agreement together with the base rate that explains it."""
    agreement = metrics.agreement
    if agreement.rate is None:
        return "n/a (no comparable pairs)"
    ci = ""
    if agreement.ci_low is not None and agreement.ci_high is not None:
        ci = f" 95% CI [{agreement.ci_low:.3f}-{agreement.ci_high:.3f}]"
    return (
        f"{agreement.agreeing_pairs}/{agreement.total_pairs}  "
        f"{agreement.rate:.3f}{ci}  (pass base rate {metrics.pass_base_rate:.3f})"
    )


def console_lines(metrics: PanelMetrics | None) -> list[str]:
    """Build the panel-agreement console block, or [] when no panel ran.

    Args:
        metrics: PanelMetrics from panel_metrics.compute_panel_metrics.
    Returns:
        Console lines, kappa first — the chance-corrected number is the headline
        and raw agreement is the secondary line, deliberately in that order.
    """
    if metrics is None:
        return []

    lines = [
        f"    Inter-judge agreement (Fleiss kappa): {_fmt_kappa(metrics.kappa)}",
        f"    Inter-judge agreement (raw pairwise): {_fmt_raw(metrics)}",
    ]

    if metrics.by_criterion:
        lines.append("      By criterion:")
        for criterion in metrics.by_criterion:
            kappa = "kappa n/a" if criterion.kappa is None else f"kappa {criterion.kappa:.3f}"
            lines.append(
                f"        {criterion.judge_kind:<16} "
                f"unanimous {criterion.unanimous}/{criterion.n_items}  {kappa}"
            )

    flips = metrics.repeat_flips
    if flips.n_records:
        lines.append(
            f"      Repeat flips across k: {flips.records_with_flips}/{flips.n_records} records "
            f"({flips.unanimous_flips} engine-driven, {flips.solo_flips} single-judge)"
        )
        for model, count in flips.flips_by_judge:
            lines.append(f"        {model:<16} flipped on {count}/{flips.n_records} records")

    return lines


def markdown_rows(metrics: PanelMetrics | None) -> list[str]:
    """Build the panel-agreement markdown table rows, or [] when no panel ran."""
    if metrics is None:
        return []

    rows = [
        f"| Inter-judge agreement (Fleiss kappa) | {_fmt_kappa(metrics.kappa)} |",
        f"| Inter-judge agreement (raw pairwise) | {_fmt_raw(metrics)} |",
    ]
    for criterion in metrics.by_criterion:
        kappa = "n/a" if criterion.kappa is None else f"{criterion.kappa:.3f}"
        rows.append(
            f"| — {criterion.judge_kind} | unanimous {criterion.unanimous}/{criterion.n_items}, "
            f"kappa {kappa} |"
        )
    flips = metrics.repeat_flips
    if flips.n_records:
        rows.append(
            f"| Repeat flips across k | {flips.records_with_flips}/{flips.n_records} records "
            f"({flips.unanimous_flips} engine-driven, {flips.solo_flips} single-judge) |"
        )
    return rows
