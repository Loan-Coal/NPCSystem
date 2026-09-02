"""
Module: evals.dashboard.headline
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Render the paired-rates headline card for the run detail page (EVAL-P13.2).
         Computes LLM-judge and deterministic pass rates with Wilson 95% CIs, reads
         calibration kappas, and gates the LLM-judge rate behind the EVAL-P11.1
         publication policy (scorer_trust_policy.check_publication).
Dependencies: html, json, pathlib (stdlib), calibration (_kappa_from_matrix,
              UndefinedKappaError, kappa_interval, BOOTSTRAP_*), calibration_records
              (CalibrationLabel), rate_stats (wilson_interval), scorer_trust_policy.
Used by: evals.dashboard.app (GET /runs/{gen_id} route).
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from calibration import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    UndefinedKappaError,
    _kappa_from_matrix,
    kappa_interval,
)
from calibration_records import CalibrationLabel
from rate_stats import wilson_interval
from scorer_trust_policy import check_publication

_NA_RATE = '<span class="na">N/A</span>'


# ---------------------------------------------------------------------------
# Calibration helpers
# ---------------------------------------------------------------------------


def _compute_kappas(rows_by_scorer: dict[str, list[dict[str, Any]]]) -> dict[str, float]:
    """Compute Cohen's κ per scorer from grouped calibration rows.

    Args:
        rows_by_scorer: Adjudicated calibration rows grouped by scorer name.
    Returns:
        {scorer: kappa}; excludes scorers with < 2 adjudicated rows or undefined κ.
    """
    result: dict[str, float] = {}
    for scorer, rows in rows_by_scorer.items():
        if len(rows) < 2:
            continue
        tp = sum(1 for r in rows if r.get("scorer_verdict") is True and r.get("human_verdict") is True)
        fp = sum(1 for r in rows if r.get("scorer_verdict") is True and r.get("human_verdict") is False)
        fn = sum(1 for r in rows if r.get("scorer_verdict") is False and r.get("human_verdict") is True)
        tn = sum(1 for r in rows if r.get("scorer_verdict") is False and r.get("human_verdict") is False)
        kappa = _kappa_or_none(tp=tp, fp=fp, fn=fn, tn=tn)
        if kappa is not None:
            result[scorer] = kappa
    return result


def _kappa_or_none(*, tp: int, fp: int, fn: int, tn: int) -> float | None:
    """Return kappa, or None when the confusion matrix leaves it undefined.

    A degenerate matrix (one verdict class empty) has no defined kappa, and such a
    scorer is omitted from the badge rather than shown as 0.0 -- a false precision
    that would read as "measured and bad" instead of "not measurable". Converting
    the raised UndefinedKappaError into an explicit sentinel here keeps that skip a
    visible branch at the call site instead of a silently swallowed exception.
    """
    try:
        return float(_kappa_from_matrix(tp=tp, fp=fp, fn=fn, tn=tn))
    except UndefinedKappaError:
        return None


def _kappas_from_labels(labels_path: Path) -> dict[str, float]:
    """Return {scorer: kappa} point estimates from a calibration labels file.

    Reads only adjudicated rows (human_verdict is not None). Skips malformed lines.

    Args:
        labels_path: Full path to labels_v1.jsonl.
    Returns:
        {scorer: kappa}; empty dict when the file is absent or has no adjudicated rows.
    """
    if not labels_path.exists():
        return {}
    rows_by_scorer: dict[str, list[dict[str, Any]]] = {}
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        row = _adjudicated_row_or_none(line)
        if row is None:
            continue
        rows_by_scorer.setdefault(str(row.get("scorer", "")), []).append(row)
    return _compute_kappas(rows_by_scorer)


def _intervals_from_labels(labels_path: Path) -> dict[str, tuple[float, float]]:
    """Return {scorer: (lo, hi)} real 95 % bootstrap CIs on κ, from the labels file.

    CR-L03-02: this replaced a hardcoded `(0.0, 0.0)` handed to `check_publication`.
    Scorers whose interval is not computable (fewer than 2 clean adjudicated rows once
    drifted rows are excluded, or a degenerate bootstrap) are simply absent from the
    result — the caller refuses them rather than inventing a bound.

    Args:
        labels_path: Full path to labels_v1.jsonl.
    Returns:
        {scorer: (lo, hi)}; empty when the file is absent or unreadable.
    """
    if not labels_path.exists():
        return {}
    rows_by_scorer: dict[str, list[Any]] = {}
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        row = _label_row_or_none(line)
        if row is None:
            continue
        rows_by_scorer.setdefault(str(row.scorer), []).append(row)
    intervals: dict[str, tuple[float, float]] = {}
    for scorer, rows in rows_by_scorer.items():
        try:
            ci = kappa_interval(rows, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
        except ValueError:
            continue
        intervals[scorer] = (ci.lo, ci.hi)
    return intervals


def _label_row_or_none(line: str) -> CalibrationLabel | None:
    """Parse one labels line into a CalibrationLabel, or None if it does not validate.

    Deliberately lenient, matching `_adjudicated_row_or_none`: labels_v1.jsonl is a
    hand-edited boundary file, and one malformed row must degrade a single scorer's
    interval, never blank the whole page. `read_calibration_labels` is the strict
    reader and raises on the first bad row, which is right for the calibration CLI
    and wrong for a dashboard render.
    """
    stripped = line.strip()
    if not stripped:
        return None
    try:
        return CalibrationLabel.model_validate(json.loads(stripped))
    except (json.JSONDecodeError, ValidationError):
        return None


def _refusal_part(scorer: str, kappa: float, interval: tuple[float, float] | None) -> str | None:
    """Render one scorer's refusal, or None when it is licensed for publication.

    A scorer with no computable interval is refused: publication requires a measured
    bound, and the absence of one is not evidence that the bound would clear the
    threshold. Synthesising a placeholder here is exactly the defect CR-L03-02 names.
    """
    if interval is None:
        return _html.escape(
            f"PolicyRefusal(scorer={scorer!r}, kappa={kappa}, interval=unmeasured, "
            f"trust_level='restricted')"
        )
    refusal = check_publication(scorer, kappa, interval)
    return None if refusal is None else _html.escape(str(refusal))


def _adjudicated_row_or_none(line: str) -> dict[str, Any] | None:
    """Parse one calibration line, or None if blank, malformed, or unadjudicated.

    labels_v1.jsonl is a hand-edited file at a system boundary, so a single bad
    line must not blank the whole badge. The skip is a returned sentinel rather
    than a swallowed exception so the caller's `if row is None: continue` makes it
    visible. ISSUE-192: the count of skipped rows is not surfaced anywhere, so silent
    data loss here is still possible.
    """
    stripped = line.strip()
    if not stripped:
        return None
    try:
        row = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(row, dict) or row.get("human_verdict") is None:
        return None
    return row


# ---------------------------------------------------------------------------
# Publication refusal
# ---------------------------------------------------------------------------


def _refusal_html(judged_rows: list[dict[str, Any]], cal_dir: Path) -> str | None:
    """Return refusal HTML if any scorer in the run fails the EVAL-P11.1 publication threshold.

    Returns None when calibration data is absent (cannot gate) or all present scorers
    are publishable (kappa >= 0.60). When a refusal fires, the caller must display
    this instead of the numeric LLM-judge rate.

    Args:
        judged_rows: Parsed rows from judged.jsonl.
        cal_dir: Directory containing labels_v1.jsonl.
    Returns:
        HTML span with refusal notice, or None when publication is licensed.
    """
    scorers = {str(r.get("judge_kind", "")) for r in judged_rows if r.get("judge_kind")}
    if not scorers:
        return None
    kappas = _kappas_from_labels(cal_dir / "labels_v1.jsonl")
    if not kappas:
        return None
    intervals = _intervals_from_labels(cal_dir / "labels_v1.jsonl")
    refusal_parts: list[str] = []
    for scorer in sorted(scorers):
        kappa = kappas.get(scorer)
        if kappa is None:
            continue
        part = _refusal_part(scorer, kappa, intervals.get(scorer))
        if part is not None:
            refusal_parts.append(part)
    if not refusal_parts:
        return None
    inner = " | ".join(refusal_parts)
    return f'<span class="refusal">calibration does not license publication: {inner}</span>'


# ---------------------------------------------------------------------------
# Rate display
# ---------------------------------------------------------------------------


def _rate_html(passes: int, total: int) -> str:
    """Render 'n/N (pct%) [CI_lo%–CI_hi%]' string with Wilson 95% CI, or N/A if total == 0.

    Args:
        passes: Number of passing records.
        total: Total number of records.
    Returns:
        Formatted HTML rate string.
    """
    if total == 0:
        return _NA_RATE
    lo, hi = wilson_interval(passes, total)
    pct = f"{passes / total:.0%}"
    return f"{passes}/{total} ({pct}) [{lo:.0%}–{hi:.0%}]"


# ---------------------------------------------------------------------------
# Card renderer
# ---------------------------------------------------------------------------


def render_headline_card(
    judged_rows: list[dict[str, Any]],
    det_rows: list[dict[str, Any]],
    meta: dict[str, Any],
    cal_dir: Path,
) -> str:
    """Render the paired-rates headline card HTML div (EVAL-P13.2).

    Displays the LLM-judge and deterministic pass rates with Wilson 95% CIs.
    If the EVAL-P11.1 publication policy denies any scorer present in judged_rows,
    the LLM-judge rate is replaced by a refusal notice. Always shows judge model,
    git SHA, and k.

    Args:
        judged_rows: Parsed rows from judged.jsonl.
        det_rows: Parsed rows from deterministic_judged.jsonl.
        meta: Run metadata dict (from meta.json).
        cal_dir: Directory containing calibration labels_v1.jsonl.
    Returns:
        HTML string: a <div class="headline-card"> block.
    """
    config = meta.get("config", {})
    judge_model = _html.escape(str(config.get("judge_model", "unknown")))
    git_sha = _html.escape(str(config.get("git_sha", "unknown")))
    k = int(meta.get("k", 0))

    llm_total = len(judged_rows)
    llm_passes = sum(1 for r in judged_rows if r.get("passed", False))
    refusal = _refusal_html(judged_rows, cal_dir)
    llm_display = refusal if refusal is not None else _rate_html(llm_passes, llm_total)

    det_total = len(det_rows)
    det_passes = sum(1 for r in det_rows if r.get("passed", False))
    det_display = _rate_html(det_passes, det_total)

    return (
        '<div class="headline-card">'
        "<h2>Headline rates</h2>"
        f"<p><strong>LLM-judge:</strong> {llm_display}"
        f"&nbsp;&nbsp;<strong>Deterministic:</strong> {det_display}</p>"
        f'<p class="card-meta">Judge:&nbsp;<code>{judge_model}</code>'
        f"&nbsp;&nbsp;SHA:&nbsp;<code>{git_sha}</code>"
        f"&nbsp;&nbsp;k={k}</p>"
        "</div>"
    )
