#!/usr/bin/env python
"""
Module: dump_openapi
Layer: scripts (dev tooling)
Purpose: Print the live OpenAPI schema, so nothing has to commit a copy of it.
         Replaces the tracked live_openapi.json deleted in R4.7, which had drifted
         four routes behind the app while looking authoritative.
Does NOT: start a server, reach Neo4j, or write into the repo by default.
Dependencies: argparse, json, pathlib, sys, npc_engine.main
Dependencies injected: None.
Used by: make openapi
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


def render(indent: int = 2) -> str:
    """Return the app's OpenAPI schema as deterministic JSON text.

    Keys are sorted so two dumps of the same app are byte-identical and a diff
    shows real schema change rather than dict ordering.

    Args:
        indent: Number of spaces per nesting level.

    Returns:
        The schema as a JSON string with a trailing newline.
    """
    from npc_engine.main import app

    return json.dumps(app.openapi(), indent=indent, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Write the schema to --out, or to stdout when --out is absent.

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].

    Returns:
        Process exit code; 0 on success.
    """
    parser = argparse.ArgumentParser(description="Dump the live OpenAPI schema (R4.7).")
    parser.add_argument("--out", type=Path, default=None, help="file to write; stdout if omitted")
    args = parser.parse_args(argv)

    text = render()
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"openapi: wrote {args.out} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
