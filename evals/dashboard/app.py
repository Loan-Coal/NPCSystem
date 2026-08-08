"""
Module: evals.dashboard.app
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: FastAPI application for the local dev-facing eval dashboard (EVAL-P7). Exposes
         GET / listing all eval runs sorted newest-first. Uses stdlib string.Template for
         HTML rendering so jinja2 is not required as a new dependency.
Dependencies: fastapi, starlette (HTMLResponse), pathlib, json, string (all stdlib or
              already-installed packages).
Used by: python -m evals dashboard (future); tests/unit/evals/test_dashboard_runs.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_DEFAULT_GENERATIONS_DIR = Path(__file__).parent.parent / "generations"

_EMPTY_STATE_MSG = "No eval runs found."


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
    """Render a list of run meta dicts as an HTML table or an empty-state paragraph.

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
        rows.append(
            "<tr>"
            f"<td>{run.get('gen_id', '')}</td>"
            f"<td>{run.get('k', '')}</td>"
            f"<td>{cfg.get('prompt_version', '')}</td>"
            f"<td>{cfg.get('git_sha', '')}</td>"
            f"<td>{run.get('generated_at', '')}</td>"
            "</tr>"
        )

    header = (
        "<thead><tr>"
        "<th>gen_id</th><th>k</th><th>prompt_version</th>"
        "<th>git_sha</th><th>timestamp</th>"
        "</tr></thead>"
    )
    return f"<table>{header}<tbody>{''.join(rows)}</tbody></table>"


def make_app(generations_dir: Path | None = None) -> FastAPI:
    """Create and return a configured eval dashboard FastAPI application.

    Args:
        generations_dir: Directory to scan for generation run meta.json files.
            Defaults to evals/generations/ relative to this package.
    Returns:
        FastAPI application with GET / wired to the runs list view.
    """
    resolved_dir = generations_dir if generations_dir is not None else _DEFAULT_GENERATIONS_DIR
    dashboard = FastAPI(title="Eval Dashboard")

    @dashboard.get("/", response_class=HTMLResponse)
    async def run_list() -> HTMLResponse:
        """Return HTML listing all eval runs sorted newest-first."""
        runs = _collect_runs(resolved_dir)
        tpl = _load_template("runs.html")
        runs_content = _render_runs_table(runs)
        html = tpl.safe_substitute(page_title="Eval Runs", runs_content=runs_content)
        return HTMLResponse(html)

    return dashboard


app = make_app()
