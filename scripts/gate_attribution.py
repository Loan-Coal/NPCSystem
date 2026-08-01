"""
Module: gate_attribution
Layer: harness
Purpose: Decide whether a red gate is THIS task's fault by diffing the currently failing
    tests against the phase-boundary baseline.
Dependencies: scripts/gate_baseline (runner + baseline I/O), scripts/loop_gates.
Used by: scripts/expand_loop.sh, scripts/classify_gate_failure.py.

Without this, a single pre-existing failure halts every task of a phase — the exact
incident (six unrelated test-isolation failures) that motivated the upstream kit's §6.5.

Exit codes:
    0  no new failures — pre-existing debt, the task may be committed and the loop continues
    1  new failures — a candidate regression, hand to gate_confirm.py before charging it
    2  the check could not be run (timeout / missing tool) — infrastructure, not a regression
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate_baseline import collect_failures, read_baseline  # noqa: E402

EXIT_NO_NEW = 0
EXIT_NEW = 1
EXIT_INFRA = 2


def new_failures(current: frozenset[str], baseline: frozenset[str]) -> frozenset[str]:
    """Failing node ids present now that were not already failing at the baseline."""
    return frozenset(current - baseline)


def main(argv: list[str] | None = None) -> int:
    """Run the HALT-class checks once and report failures new since the baseline."""
    parser = argparse.ArgumentParser(description="Attribute a red gate against the baseline.")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable summary")
    args = parser.parse_args(argv)

    current, results = collect_failures(runs=1)
    baseline = read_baseline()
    introduced = new_failures(current, baseline)

    if any(r.returncode in (124, 127) for r in results):
        print("ATTRIBUTION=INFRA", file=sys.stderr)
        return EXIT_INFRA

    if args.json:
        print(
            json.dumps(
                {
                    "current": sorted(current),
                    "baseline": sorted(baseline),
                    "new": sorted(introduced),
                },
                indent=2,
            )
        )
    else:
        verdict = "NEW_FAILURES" if introduced else "BASELINE_RED" if current else "GREEN"
        print(f"ATTRIBUTION={verdict} NEW={len(introduced)} CURRENT={len(current)}")
        for node_id in sorted(introduced):
            print(f"NEW_FAILURE {node_id}")

    return EXIT_NEW if introduced else EXIT_NO_NEW


if __name__ == "__main__":
    raise SystemExit(main())
