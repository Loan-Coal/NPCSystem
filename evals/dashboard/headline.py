"""
Module: evals.dashboard.headline
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Render the paired-rates headline card for the run detail page (EVAL-P13.2).
         Computes LLM-judge and deterministic pass rates with Wilson 95% CIs, reads
         calibration kappas, and gates the LLM-judge rate behind the EVAL-P11.1
         publication policy (scorer_trust_policy.check_publication).
Dependencies: html, json, pathlib (stdlib), calibration (_kappa_from_matrix,
              UndefinedKappaError), rate_stats (wilson_interval), scorer_trust_policy.
Used by: evals.dashboard.app (GET /runs/{gen_id} route).
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Any

from calibration import UndefinedKappaError, _kappa_from_matrix
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
    refusal_parts: list[str] = []
    for scorer in sorted(scorers):
        kappa = kappas.get(scorer)
        if kappa is None:
            continue
        refusal = check_publication(scorer, kappa, (0.0, 0.0))
        if refusal is not None:
            refusal_parts.append(_html.escape(str(refusal)))
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
