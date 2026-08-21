"""
Module: cli
Layer: evals (eval harness — not part of src/)
Purpose: Serve the EVAL-P7 eval dashboard over HTTP, so `python -m evals dashboard`
         — the invocation DECISIONS.md:73 and ROADMAP.md:997 have always documented —
         actually resolves. The app, its templates and its tests shipped with
         EVAL-P7.1-P7.3 and EVAL-P13.2 but no verb was ever registered, leaving it
         built, tested and unreachable.
Dependencies: argparse, pathlib (stdlib); uvicorn; dashboard.app (make_app)
Used by: evals/__main__.py VERBS["dashboard"]; tests/unit/evals/test_cli_dispatch.py

Lives in its own module rather than in app.py because app.py is at 294 lines
against the 300-line non-test cap, and a serving entry point is a distinct
responsibility from the app factory (SRP: handler vs adapter).
"""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 8050

_EXIT_OK: int = 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the dashboard verb."""
    parser = argparse.ArgumentParser(
        prog="python -m evals dashboard",
        description=(
            "Serve the local eval dashboard: run list, run detail with the headline "
            "card and flakiness table, and per-case drill-down."
        ),
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Interface to bind. Default {DEFAULT_HOST} (loopback — this is a dev tool).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=(
            f"Port to bind. Default {DEFAULT_PORT}, deliberately not 8000 — that is the "
            "engine's port and the demo designer dashboard is served from it."
        ),
    )
    parser.add_argument(
        "--generations-dir",
        type=Path,
        default=None,
        help="Directory of generation runs to list. Defaults to evals/generations/.",
    )
    parser.add_argument(
        "--calibration-dir",
        type=Path,
        default=None,
        help="Directory holding labels_v1.jsonl. Defaults to evals/calibration/.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Serve the eval dashboard until interrupted.

    Args:
        argv: Argument list; defaults to sys.argv[1:] via argparse.
    Returns:
        0 once the server stops. Never returns while serving.
    Raises:
        SystemExit: argparse raises this for --help and for a bad argument.
    """
    args = _build_parser().parse_args(argv)

    # Imported here, not at module scope, so `python -m evals --help` stays cheap
    # and cannot fail on a machine where uvicorn's optional extras are unhappy —
    # the same reason __main__.py imports every verb target lazily.
    import uvicorn

    from dashboard.app import make_app

    app = make_app(
        generations_dir=args.generations_dir,
        calibration_dir=args.calibration_dir,
    )
    # Nothing is written to stdout here: log_level="info" makes uvicorn announce
    # the bound address itself, and a bare stdout write would be a new R002
    # violation in evals/.
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return _EXIT_OK
