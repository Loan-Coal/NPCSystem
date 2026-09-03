#!/usr/bin/env python
"""
Module: check_api_contract
Layer: scripts (dev tooling)
Purpose: Fail when the /v1 surface changes in a way that breaks an existing consumer.
         Additive change passes untouched and needs no baseline edit; only a break
         reds, and only a deliberate break requires re-recording.
Does NOT: judge behaviour, latency, or error text — only the declared shape.
Dependencies: argparse, json, pathlib, sys, api_contract_differ, api_contract_extractor,
              api_contract_models
Dependencies injected: None.
Used by: make check-api-contract, tests/unit/scripts/test_api_contract_differ.py

Why a committed baseline here does not repeat R4.7's live_openapi.json: that file had
no reader, so only human diligence kept it current and it lost four routes. This one is
the input of a gate that runs in `make check` on every commit, so its only two reachable
states are "equal to the app" and "red". See DEC-253.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from api_contract_differ import diff_contracts
from api_contract_extractor import build_contract
from api_contract_models import ApiContract

BASELINE_PATH = Path(__file__).resolve().parent / "api_contract_baseline.json"


def render(contract: ApiContract) -> str:
    """Return the contract as deterministic JSON text with a trailing newline."""
    return json.dumps(contract.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def load_baseline(path: Path = BASELINE_PATH) -> ApiContract | None:
    """Return the recorded contract, or None when no baseline has been written yet."""
    if not path.exists():
        return None
    return ApiContract.model_validate_json(path.read_text(encoding="utf-8"))


def write_baseline(contract: ApiContract, path: Path = BASELINE_PATH) -> None:
    """Record the current contract as the accepted baseline."""
    path.write_text(render(contract), encoding="utf-8", newline="\n")
    print(f"check-api-contract: baseline updated -> {path.name}")


def format_report(breaks: list[object], operations: int, schemas: int) -> str:
    """Return the human-readable gate report."""
    if not breaks:
        return f"check-api-contract: OK - {operations} operations, {schemas} schemas, no breaking change.\n"
    lines = [f"check-api-contract: {len(breaks)} breaking change(s) to the /v1 surface:"]
    lines += [item.render() for item in breaks]  # type: ignore[attr-defined]
    lines.append("")
    lines.append("A consumer built against the recorded contract would stop working. Either:")
    lines.append("  1. make the change additive instead, or")
    lines.append("  2. follow docs/API_STABILITY.md, then re-record with:")
    lines.append("       python scripts/check_api_contract.py --update")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Compare the live contract to the baseline; return 1 on a breaking change."""
    parser = argparse.ArgumentParser(description="API breaking-change gate (R5.1).")
    parser.add_argument("--update", action="store_true", help="Accept the current surface.")
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    args = parser.parse_args(argv)

    current = build_contract()
    if args.update:
        write_baseline(current, args.baseline)
        return 0

    baseline = load_baseline(args.baseline)
    if baseline is None:
        print(f"check-api-contract: no baseline at {args.baseline}; record one with --update")
        return 1

    breaks = diff_contracts(baseline, current)
    print(format_report(list(breaks), len(current.operations), len(current.schemas)))
    return 1 if breaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
