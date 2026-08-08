"""
Module: evals.dashboard.app
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: FastAPI application for the local dev-facing eval dashboard (EVAL-P7). Exposes
         GET / (run list), GET /runs/{gen_id} (run detail), and
         GET /runs/{gen_id}/case?record_id=… (per-case k-repetition drill-down).
         Uses stdlib string.Template for HTML rendering — no jinja2 required.
Dependencies: fastapi, starlette (HTMLResponse, HTTPException), pathlib, json, html,
              string, evals.dashboard.detail (all stdlib or already-installed packages).
Used by: python -m evals dashboard (future); tests/unit/evals/.
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path
from string import Template
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from evals.dashboard.detail import (
    compute_case_stats,
    read_judged_rows,
    render_calibration_badge,
    render_flaky_table,
)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_DEFAULT_GENERATIONS_DIR = Path(__file__).parent.parent / "generations"
_DEFAULT_CALIBRATION_DIR = Path(__file__).parent.parent / "calibration"

_EMPTY_STATE_MSG = "No eval runs found."
_DET_RATES_NA = '<span class="na">N/A — run <code>make eval-score</code> to compute</span>'


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _load_template(name: str) -> Template:
    """Read a template file and return a stdlib Template instance.

    Args:
        name: Filename within the templates directory.
    Returns:
        stdlib Template ready for safe_substitute().
    """
    content = (_TEMPLATES_DIR / name).read_text(encoding="utf-8")
    return Template(content)


def _read_meta(path: Path) -> dict[str, Any] | None:
    """Parse a meta.json file, returning None on any read or parse failure.

    Args:
        path: Path to the meta.json file.
    Returns:
        Parsed dict, or None if the file cannot be read or is not valid JSON.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Run list helpers
# ---------------------------------------------------------------------------


def _collect_runs(generations_dir: Path) -> list[dict[str, Any]]:
    """Glob generations_dir for meta.json files and sort newest-first.

    Args:
        generations_dir: Directory whose subdirectories each contain a meta.json.
    Returns:
        List of parsed meta dicts sorted by generated_at descending.
    """
    runs: list[dict[str, Any]] = []
    for meta_path in generations_dir.glob("*/meta.json"):
        meta = _read_meta(meta_path)
        if meta is not None:
            runs.append(meta)
    runs.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
    return runs


def _render_runs_table(runs: list[dict[str, Any]]) -> str:
    """Render run meta dicts as an HTML table or empty-state paragraph.

    Args:
        runs: List of parsed meta dicts, expected newest-first.
    Returns:
        HTML string containing either a full <table> or a .empty-state <p>.
    """
    if not runs:
        return f'<p class="empty-state">{_EMPTY_STATE_MSG}</p>'

    rows: list[str] = []
    for run in runs:
        cfg = run.get("config", {})
        gen_id = _html.escape(str(run.get("gen_id", "")))
        rows.append(
            "<tr>"
            f'<td><a href="/runs/{gen_id}">{gen_id}</a></td>'
            f"<td>{_html.escape(str(run.get('k', '')))}</td>"
            f"<td>{_html.escape(str(cfg.get('prompt_version', '')))}</td>"
            f"<td>{_html.escape(str(cfg.get('git_sha', '')))}</td>"
            f"<td>{_html.escape(str(run.get('generated_at', '')))}</td>"
            "</tr>"
        )

    header = (
        "<thead><tr>"
        "<th>gen_id</th><th>k</th><th>prompt_version</th>"
        "<th>git_sha</th><th>timestamp</th>"
        "</tr></thead>"
    )
    return f"<table>{header}<tbody>{''.join(rows)}</tbody></table>"


# ---------------------------------------------------------------------------
# Case detail helpers
# ---------------------------------------------------------------------------

_VERDICT_CSS: dict[bool | None, tuple[str, str]] = {
    True: ("pass", "PASS"),
    False: ("fail", "FAIL"),
    None: ("unknown", "?"),
}


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            pass
    return rows


def _read_output_rows(gen_dir: Path, record_id: str) -> list[dict[str, Any]]:
    """Read outputs.jsonl for record_id, sorted by repetition; empty list if absent."""
    path = gen_dir / "outputs.jsonl"
    if not path.exists():
        return []
    rows = [r for r in _parse_jsonl(path) if r.get("record_id") == record_id]
    rows.sort(key=lambda r: int(r.get("repetition", 0)))
    return rows


def _read_judged_by_rep(gen_dir: Path, record_id: str) -> dict[int, dict[str, Any]]:
    """Build {repetition: judged_row} map for one record_id."""
    return {
        int(r.get("repetition", 0)): r
        for r in read_judged_rows(gen_dir)
        if r.get("record_id") == record_id
    }


def _render_single_pane(row: dict[str, Any], judged: dict[str, Any], rep: int) -> str:
    """Render one repetition pane with data-rep attr, response, context keys, reasoning."""
    passed: bool | None = judged.get("passed")
    verdict_cls, verdict_label = _VERDICT_CSS.get(passed, ("unknown", "?"))
    npc_response = _html.escape(str(row.get("npc_response", "")))
    reasoning = _html.escape(str(judged.get("reasoning", "")))
    ctx_items: list[dict[str, Any]] = row.get("retrieved_context", [])
    ctx_keys_html = "".join(
        f'<li><code>{_html.escape(str(item.get("key", "")))}</code></li>'
        for item in ctx_items
    )
    return (
        f'<div class="pane" data-rep="{rep}">'
        f'<h3>Repetition {rep} <span class="verdict {verdict_cls}">{verdict_label}</span></h3>'
        f"<p><strong>Response:</strong></p><pre>{npc_response}</pre>"
        f"<p><strong>Context keys:</strong></p><ul>{ctx_keys_html}</ul>"
        f"<p><strong>Reasoning:</strong></p><pre>{reasoning}</pre>"
        f"</div>"
    )


def _render_case_panes(
    output_rows: list[dict[str, Any]],
    judged_by_rep: dict[int, dict[str, Any]],
) -> str:
    """Render all repetition panes in a side-by-side flex container."""
    panes: list[str] = []
    for row in output_rows:
        rep = int(row.get("repetition", 0))
        panes.append(_render_single_pane(row, judged_by_rep.get(rep, {}), rep))
    return f'<div class="panes-container">{"".join(panes)}</div>'


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def make_app(
    generations_dir: Path | None = None,
    calibration_dir: Path | None = None,
) -> FastAPI:
    """Create and return a configured eval dashboard FastAPI application.

    Args:
        generations_dir: Directory to scan for generation run meta.json files.
            Defaults to evals/generations/ relative to this package.
        calibration_dir: Directory containing calibration labels_v1.jsonl.
            Defaults to evals/calibration/ relative to this package.
    Returns:
        FastAPI application with GET /, GET /runs/{gen_id}, and GET /runs/{gen_id}/case routes.
    """
    resolved_dir = generations_dir if generations_dir is not None else _DEFAULT_GENERATIONS_DIR
    resolved_cal = calibration_dir if calibration_dir is not None else _DEFAULT_CALIBRATION_DIR
    dashboard = FastAPI(title="Eval Dashboard")

    @dashboard.get("/", response_class=HTMLResponse)
    async def run_list() -> HTMLResponse:
        """Return HTML listing all eval runs sorted newest-first."""
        runs = _collect_runs(resolved_dir)
        tpl = _load_template("runs.html")
        runs_content = _render_runs_table(runs)
        body = tpl.safe_substitute(page_title="Eval Runs", runs_content=runs_content)
        return HTMLResponse(body)

    @dashboard.get("/runs/{gen_id}", response_class=HTMLResponse)
    async def run_detail(gen_id: str) -> HTMLResponse:
        """Return the detail page for one generation run."""
        gen_dir = resolved_dir / gen_id
        if not (gen_dir / "meta.json").exists():
            raise HTTPException(status_code=404, detail=f"Run {gen_id!r} not found.")

        meta = _read_meta(gen_dir / "meta.json") or {}
        k = int(meta.get("k", 0))
        config = meta.get("config", {})
        judged_rows = read_judged_rows(gen_dir)

        total = len(judged_rows)
        passes = sum(1 for r in judged_rows if r.get("passed", False))
        pass_rate_pct = f"{passes / total:.0%}" if total > 0 else "N/A"

        flaky_table = render_flaky_table(compute_case_stats(judged_rows))
        cal_badge = render_calibration_badge(resolved_cal)
        config_block = _html.escape(json.dumps(config, indent=2))

        tpl = _load_template("run_detail.html")
        body = tpl.safe_substitute(
            page_title=f"Run: {gen_id}",
            gen_id=_html.escape(gen_id),
            k=k,
            pass_rate_pct=pass_rate_pct,
            passes=passes,
            total=total,
            calibration_badge=cal_badge,
            deterministic_rates=_DET_RATES_NA,
            config_block=config_block,
            flaky_table=flaky_table,
        )
        return HTMLResponse(body)

    @dashboard.get("/runs/{gen_id}/case", response_class=HTMLResponse)
    async def case_detail(gen_id: str, record_id: str = Query(...)) -> HTMLResponse:
        """Return the per-case drill-down page showing all k repetitions side by side."""
        gen_dir = resolved_dir / gen_id
        if not (gen_dir / "meta.json").exists():
            raise HTTPException(status_code=404, detail=f"Run {gen_id!r} not found.")
        output_rows = _read_output_rows(gen_dir, record_id)
        if not output_rows:
            raise HTTPException(status_code=404, detail=f"Case {record_id!r} not found.")
        judged_by_rep = _read_judged_by_rep(gen_dir, record_id)
        panes_html = _render_case_panes(output_rows, judged_by_rep)
        tpl = _load_template("case_detail.html")
        body = tpl.safe_substitute(
            page_title=f"Case: {record_id}",
            gen_id=_html.escape(gen_id),
            record_id=_html.escape(record_id),
            panes=panes_html,
        )
        return HTMLResponse(body)

    return dashboard


app = make_app()
