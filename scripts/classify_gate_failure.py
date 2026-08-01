"""
Module: classify_gate_failure
Layer: harness
Purpose: Route a red `make check` to a bounded repair session (AUTOFIX) or to a human
    (HALT), by re-running the gate's constituents individually.
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
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate_baseline import failing_node_ids, run_check  # noqa: E402
from loop_gates import AUTOFIX_CHECK_SPECS, HALT_CHECK_SPECS  # noqa: E402

EXIT_AUTOFIX = 0
EXIT_HALT = 1
EXIT_UNATTRIBUTED = 3


def first_red(specs: tuple[tuple[str, tuple[str, ...]], ...]) -> tuple[str, str] | None:
    """Run specs in order and return ``(name, output)`` for the first that fails."""
    for name, argv in specs:
        result = run_check(name, argv)
        if not result.ok:
            return name, result.output
    return None


def main(argv: list[str] | None = None) -> int:
    """Classify the current red gate and print a one-line verdict plus evidence."""
    parser = argparse.ArgumentParser(description="Route a red gate to AUTOFIX or HALT.")
    parser.add_argument("--quiet", action="store_true", help="suppress failing-test detail")
    args = parser.parse_args(argv)

    halt = first_red(HALT_CHECK_SPECS)
    if halt is not None:
        name, output = halt
        print(f"CLASSIFICATION=HALT FAILED_CHECK={name}")
        if not args.quiet:
            for node_id in sorted(failing_node_ids(output)):
                print(f"FAILING {node_id}")
        return EXIT_HALT

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
