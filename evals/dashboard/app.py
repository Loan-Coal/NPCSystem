"""
Module: evals.dashboard.app
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: FastAPI application for the local dev-facing eval dashboard (EVAL-P7). Exposes
         GET / listing all eval runs sorted newest-first, and GET /runs/{gen_id} for the
         run-detail view (pass rate, calibration badge, deterministic rates, flaky table).
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

from fastapi import FastAPI, HTTPException
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
        FastAPI application with GET / and GET /runs/{gen_id} routes.
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

    return dashboard


app = make_app()
