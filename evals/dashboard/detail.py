"""
Module: evals.dashboard.detail
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Run-detail rendering helpers for the eval dashboard. Computes per-case
         flakiness stats from judged.jsonl, reads calibration kappas from
         labels_v1.jsonl, and renders the HTML fragments used by the detail view.
Dependencies: json, html (stdlib), pathlib, typing.
Used by: evals.dashboard.app (GET /runs/{gen_id} route).
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Any

from calibration import UndefinedKappaError, _kappa_from_matrix

# Instability sort order: flaky surfaces first, stable_pass last.
_INSTABILITY_ORDER: dict[str, int] = {"flaky": 0, "stable_fail": 1, "stable_pass": 2}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_case(passes: int, k: int) -> str:
    """Return stability class for a k-repeat eval slot.

    Args:
        passes: Number of passing repetitions (0 ≤ passes ≤ k).
        k: Total repetitions (must be > 0).
    Returns:
        One of 'stable_pass', 'stable_fail', or 'flaky'.
    """
    if passes == k:
        return "stable_pass"
    if passes == 0:
        return "stable_fail"
    return "flaky"


# ---------------------------------------------------------------------------
# Judged-record reading + aggregation
# ---------------------------------------------------------------------------


def read_judged_rows(gen_dir: Path) -> list[dict[str, Any]]:
    """Read judged.jsonl from gen_dir, skipping malformed lines.

    Args:
        gen_dir: Generation directory containing judged.jsonl.
    Returns:
        List of parsed row dicts; empty list if file absent.
    """
    path = gen_dir / "judged.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError:
            pass
    return rows


def compute_case_stats(judged_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group judged rows by record_id and sort by instability (flaky first).

    Args:
        judged_rows: Parsed rows from judged.jsonl.
    Returns:
        List of per-case stat dicts sorted by instability order.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in judged_rows:
        rid = str(row.get("record_id", ""))
        groups.setdefault(rid, []).append(row)

    stats: list[dict[str, Any]] = []
    for record_id, rows in groups.items():
        k = len(rows)
        passes = sum(1 for r in rows if r.get("passed", False))
        classification = classify_case(passes, k)
        stats.append(
            {
                "record_id": record_id,
                "k": k,
                "passes": passes,
                "pass_rate": passes / k,
                "classification": classification,
                "order": _INSTABILITY_ORDER.get(classification, 2),
            }
        )
    return sorted(stats, key=lambda s: s["order"])


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def render_flaky_table(case_stats: list[dict[str, Any]]) -> str:
    """Render case stats as an HTML table, flaky cases first.

    Args:
        case_stats: Output of compute_case_stats().
    Returns:
        HTML table string, or empty-state paragraph if no cases.
    """
    if not case_stats:
        return '<p class="empty-state">No judged records found.</p>'

    rows: list[str] = []
    for cs in case_stats:
        cls = _html.escape(cs["classification"])
        rid = _html.escape(cs["record_id"])
        rate_str = f"{cs['passes']}/{cs['k']} ({cs['pass_rate']:.0%})"
        rows.append(
            f'<tr class="{cls}">'
            f"<td>{rid}</td>"
            f"<td>{rate_str}</td>"
            f'<td class="{cls}">{cls}</td>'
            "</tr>"
        )

    header = (
        "<thead><tr>"
        "<th>record_id</th><th>pass rate</th><th>classification</th>"
        "</tr></thead>"
    )
    return f"<table>{header}<tbody>{''.join(rows)}</tbody></table>"


def render_calibration_badge(calibration_dir: Path) -> str:
    """Render per-scorer kappa badge HTML from the calibration labels file.

    Reads labels_v1.jsonl, groups by scorer, computes headline κ
    (scorer_verdict vs human_verdict) for scorers with ≥2 adjudicated rows.

    Args:
        calibration_dir: Directory containing labels_v1.jsonl.
    Returns:
        HTML div with κ per scorer, or an N/A note when data is absent.
    """
    labels_path = calibration_dir / "labels_v1.jsonl"
    if not labels_path.exists():
        return '<p class="na">calibration: N/A (no labels file)</p>'

    rows_by_scorer: dict[str, list[dict[str, Any]]] = {}
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
            scorer = str(row.get("scorer", "unknown"))
            rows_by_scorer.setdefault(scorer, []).append(row)
        except json.JSONDecodeError:
            pass

    parts = _compute_kappa_parts(rows_by_scorer)
    if not parts:
        return '<p class="na">calibration: N/A (no adjudicated rows)</p>'

    items_html = "".join(f"<li>{_html.escape(p)}</li>" for p in parts)
    return (
        f'<div class="calibration-badge">'
        f"<strong>Calibration &#954; per scorer</strong>"
        f"<ul>{items_html}</ul></div>"
    )


def _compute_kappa_parts(rows_by_scorer: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Compute per-scorer kappa strings for adjudicated calibration rows.

    Args:
        rows_by_scorer: Calibration rows grouped by scorer name.
    Returns:
        List of formatted strings like 'tone_judge: κ=0.720 (n=85)'.
    """
    parts: list[str] = []
    for scorer in sorted(rows_by_scorer):
        adj = [r for r in rows_by_scorer[scorer] if r.get("human_verdict") is not None]
        if len(adj) < 2:
            continue
        tp = sum(1 for r in adj if r.get("scorer_verdict") is True and r.get("human_verdict") is True)
        fp = sum(1 for r in adj if r.get("scorer_verdict") is True and r.get("human_verdict") is False)
        fn = sum(1 for r in adj if r.get("scorer_verdict") is False and r.get("human_verdict") is True)
        tn = sum(1 for r in adj if r.get("scorer_verdict") is False and r.get("human_verdict") is False)
        n = tp + fp + fn + tn
        if n == 0:
            continue
        try:
            kappa = _kappa_from_matrix(tp=tp, fp=fp, fn=fn, tn=tn)
            parts.append(f"{scorer}: κ={kappa:.3f} (n={n})")
        except UndefinedKappaError:
            parts.append(f"{scorer}: κ undefined (no variance in scorer output) (n={n})")
    return parts
