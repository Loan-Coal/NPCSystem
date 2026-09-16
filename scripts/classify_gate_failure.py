"""
Module: classify_gate_failure
Layer: harness
Purpose: Route a red `make check` to a bounded repair session (AUTOFIX), to a human
    (HALT), or to skip-and-log (HARNESS), by re-running the gate's constituents individually.
Dependencies: scripts/loop_gates (specs), scripts/gate_baseline (runner + parsing).
Used by: scripts/expand_loop.sh.

HALT-class checks run FIRST, so reaching the AUTOFIX phase at all proves every test is
already green — a repair session can then only be looking at form, never behaviour.

Exit codes:
    0  AUTOFIX      — a form check is red; one bounded /fix-make-failure session is allowed
    1  HALT         — a behaviour check is red; never auto-repaired
    3  UNATTRIBUTED — every constituent is green though `make check` was red (in practice
                      the coverage floor). Treated as HALT-class: coverage is closed by
                      writing real tests, which is behaviour, not form.
    4  HARNESS      — the tests are red, and EVERY failing test is a harness self-test
                      (loop_gates.HARNESS_TEST_PATH_PREFIXES). Skip-and-log at the phase
                      gate; a mixed or unparseable failure is HALT (T0.3).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate_baseline import failing_node_ids, run_check  # noqa: E402
from loop_gates import (  # noqa: E402
    AUTOFIX_CHECK_SPECS,
    HALT_CHECK_SPECS,
    HARNESS_TEST_PATH_PREFIXES,
)

EXIT_AUTOFIX = 0
EXIT_HALT = 1
EXIT_UNATTRIBUTED = 3
EXIT_HARNESS = 4


def first_red(specs: tuple[tuple[str, tuple[str, ...]], ...]) -> tuple[str, str] | None:
    """Run specs in order and return ``(name, output)`` for the first that fails."""
    for name, argv in specs:
        result = run_check(name, argv)
        if not result.ok:
            return name, result.output
    return None


def is_harness_only(node_ids: frozenset[str]) -> bool:
    """True iff there is at least one failure and every one is a harness self-test.

    Non-empty is load-bearing: a crashed run (INTERNALERROR) names no node, and an empty set
    would otherwise read as "all failures are harness" and skip a broken suite.
    """
    return bool(node_ids) and all(n.startswith(HARNESS_TEST_PATH_PREFIXES) for n in node_ids)


def main(argv: list[str] | None = None) -> int:
    """Classify the current red gate and print a one-line verdict plus evidence."""
    parser = argparse.ArgumentParser(description="Route a red gate to AUTOFIX, HALT or HARNESS.")
    parser.add_argument("--quiet", action="store_true", help="suppress failing-test detail")
    args = parser.parse_args(argv)

    halt = first_red(HALT_CHECK_SPECS)
    if halt is not None:
        name, output = halt
        node_ids = failing_node_ids(output)
        harness = is_harness_only(node_ids)
        print(f"CLASSIFICATION={'HARNESS' if harness else 'HALT'} FAILED_CHECK={name}")
        if not args.quiet:
            for node_id in sorted(node_ids):
                print(f"FAILING {node_id}")
        return EXIT_HARNESS if harness else EXIT_HALT

    autofix = first_red(AUTOFIX_CHECK_SPECS)
    if autofix is not None:
        name, output = autofix
        print(f"CLASSIFICATION=AUTOFIX FAILED_CHECK={name}")
        if not args.quiet:
            sys.stdout.write(output[-4000:])
        return EXIT_AUTOFIX

    print("CLASSIFICATION=UNATTRIBUTED FAILED_CHECK=coverage-or-unknown")
    return EXIT_UNATTRIBUTED


if __name__ == "__main__":
    raise SystemExit(main())
