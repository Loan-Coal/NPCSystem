"""
Module: battery_trust
Layer: evals (eval harness — not part of the npc_engine layer model)
Purpose: Map each published battery to the judge-calibrated scorers whose verdicts
         feed it, and combine each scorer's scorer_trust_policy.check_publication
         result into one per-battery publication decision. This is the wiring
         docs/SCORER_TRUST_POLICY.md requires and that evals/summary.py, evals/report.py
         and evals/headline_refusal.py did not apply before 2026-09-05 — measured
         2026-09-04: zero references to scorer_trust_policy anywhere on the
         report-generation path (evals/report.py -> evals/summary.py ->
         evals/headline_refusal.py), so a scorer sitting below the publish threshold
         (e.g. tone_judge at kappa 0.849, CI floor -0.010) still had its battery's rate
         printed unqualified.
Dependencies: dataclasses, pathlib, calibration (run_calibration), calibration_records
              (LABELS_FILE, read_calibration_labels), scorer_trust_policy (TrustLevel,
              PolicyRefusal, check_publication), trend_store (ScorerKappa), typing
Used by: evals/summary.py (format_summary_lines, format_summary_markdown),
         evals/report.py (write_report — loads real kappas for the published report)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from calibration import run_calibration
from calibration_records import LABELS_FILE, read_calibration_labels
from scorer_trust_policy import PolicyRefusal, TrustLevel, check_publication
from trend_store import ScorerKappa

# ---------------------------------------------------------------------------
# The battery -> judged-scorer map (declared, not derived — DEC-249)
# ---------------------------------------------------------------------------

BATTERY_JUDGED_SCORERS: dict[str, tuple[str, ...]] = {
    "adversarial": ("affirms_judge", "commits_judge"),
    "anti_hallucination": ("anti_hallucination_grounded",),
    "capability": ("tone_judge",),
}
"""Which judge-calibrated scorers contribute verdicts to each published battery.

Read off the `kind:` fields in evals/cases/case_adv_*.yaml, case_neg_*.yaml and
case_pos_*.yaml (measured 2026-09-05). Purely mechanical matchers — schema,
keyword_none, keyword_any, in_set, range — are deliberately excluded: they carry
no Cohen's kappa, so check_publication has nothing to gate on them. refusal_judge
is absent from `capability` on purpose: no current case_pos_* case exercises it
(M3.2/refusal_judge stays halted, ISSUE-276).
"""


@dataclass(frozen=True)
class BatteryTrustStatus:
    """One battery's combined publication decision across its judged scorers.

    Attributes:
        level: The worst TrustLevel among the battery's contributing scorers;
            PUBLISHABLE when none refused (including when none had any recorded
            kappa at all — absence of evidence is not a refusal).
        refusals: The PolicyRefusal for every contributing scorer that
            check_publication refused, in BATTERY_JUDGED_SCORERS order. Empty
            when level is PUBLISHABLE.
    """

    level: TrustLevel
    refusals: tuple[PolicyRefusal, ...]


def battery_publication_status(
    battery: str,
    scorer_kappas: Sequence[ScorerKappa],
) -> BatteryTrustStatus:
    """Combine check_publication across one battery's contributing judged scorers.

    A scorer named in BATTERY_JUDGED_SCORERS[battery] with no matching ScorerKappa
    row — never calibrated, or refused upstream by label_adequacy.check_label_adequacy
    — is skipped: there is no measurement to gate on, which is absence of evidence,
    not evidence of untrustworthiness (mirrors headline_refusal.refusal_for_battery's
    rule for an unmeasured null baseline).

    Args:
        battery: One of the keys in BATTERY_JUDGED_SCORERS ('adversarial',
            'anti_hallucination', 'capability'). An unknown battery name
            contributes no scorers and is always PUBLISHABLE.
        scorer_kappas: Calibration kappas to check against, e.g. from a
            TrendRow.scorer_kappas or trend_row_builder's per-run computation.
    Returns:
        A BatteryTrustStatus naming the worst level among contributing scorers
        (HIDDEN outranks RESTRICTED outranks PUBLISHABLE) and the refusals that
        produced it.
    """
    by_scorer = {k.scorer: k for k in scorer_kappas}
    refusals: list[PolicyRefusal] = []
    for scorer in BATTERY_JUDGED_SCORERS.get(battery, ()):
        row = by_scorer.get(scorer)
        if row is None:
            continue
        refusal = check_publication(scorer, row.kappa, (row.ci_low, row.ci_high))
        if refusal is not None:
            refusals.append(refusal)
    if not refusals:
        return BatteryTrustStatus(TrustLevel.PUBLISHABLE, ())
    worst = TrustLevel.HIDDEN if any(r.trust_level == TrustLevel.HIDDEN for r in refusals) else TrustLevel.RESTRICTED
    return BatteryTrustStatus(worst, tuple(refusals))


def load_current_scorer_kappas(labels_path: Path = LABELS_FILE) -> tuple[ScorerKappa, ...]:
    """Compute every calibrated scorer's kappa from the on-disk labels file.

    The report-writing counterpart of trend_row_builder._scorer_kappas: same
    underlying computation (calibration.run_calibration, which applies
    label_adequacy.check_label_adequacy per scorer), called from the report path
    instead of the trend path so write_report can gate the battery it is about to
    render without needing a TrendRow.

    Args:
        labels_path: Calibration labels file; defaults to the real artifact.
            Missing file yields no kappas (every battery renders ungated), not an
            error — an uncalibrated run still produces a valid report.
    Returns:
        One ScorerKappa per scorer whose labels clear check_label_adequacy.
    """
    if not labels_path.exists():
        return ()
    labels = read_calibration_labels(labels_path)
    reports = run_calibration(labels, print_fn=lambda *_a, **_k: None)
    return tuple(
        ScorerKappa(scorer=r.scorer, kappa=r.kappa, ci_low=r.kappa_lo, ci_high=r.kappa_hi, n=r.counts.n)
        for r in reports
    )


def _format_refusals(refusals: tuple[PolicyRefusal, ...]) -> str:
    """Render a battery's refusals as one comma-joined clause."""
    return ", ".join(str(r) for r in refusals)


def trust_gate(
    battery: str,
    current_str: str,
    scorer_kappas: Sequence[ScorerKappa],
) -> str:
    """Apply the scorer trust policy to one battery's already-rendered rate string.

    Args:
        battery: One of the keys in BATTERY_JUDGED_SCORERS.
        current_str: The rate string computed so far (already null-baseline gated
            by headline_refusal, when applicable).
        scorer_kappas: Calibration kappas to check the battery's judged scorers
            against; see battery_publication_status.
    Returns:
        current_str unchanged when every contributing scorer is PUBLISHABLE (or
        the battery has none); a HIDDEN refusal message in place of current_str
        when any contributing scorer is HIDDEN; current_str with a RESTRICTED
        caveat appended when the worst contributing scorer is RESTRICTED but
        none is HIDDEN.
    """
    status = battery_publication_status(battery, scorer_kappas)
    if status.level == TrustLevel.PUBLISHABLE:
        return current_str
    clause = _format_refusals(status.refusals)
    if status.level == TrustLevel.HIDDEN:
        return f"HIDDEN — scorer trust policy refuses publication: {clause}"
    return f"{current_str}  [RESTRICTED — not publishable: {clause}]"
