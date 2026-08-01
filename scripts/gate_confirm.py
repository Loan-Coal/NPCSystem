"""
Module: gate_confirm
Layer: harness
Purpose: Re-run a specific set of failing tests to prove a candidate regression is real
    and not a flake, before the loop charges it to a task.
Dependencies: scripts/gate_baseline (runner), scripts/loop_gates (interpreter path).
Used by: scripts/expand_loop.sh, scripts/classify_gate_failure.py.

Only a failure that reproduces on a second consecutive run is charged to the task. This
is what stops one flaky test from costing a phase — the upstream kit's §6.6 incident,
where an irreversible cutover task was forfeited over two flakes it never touched.

Exit codes:
    0  nothing reproduced — flake, treat the task as complete
    1  at least one failure reproduced — confirmed regression
    2  the re-run could not be performed (timeout / missing tool)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate_baseline import failing_node_ids, run_check  # noqa: E402
from loop_gates import python_executable  # noqa: E402

EXIT_FLAKE = 0
EXIT_CONFIRMED = 1
EXIT_INFRA = 2
RERUN_ARGS = ("-q", "--tb=no", "-rf", "-p", "no:randomly")


def rerun(node_ids: list[str]) -> tuple[frozenset[str], int]:
    """Re-run exactly the given node ids.

    Args:
        node_ids: pytest node ids to re-execute.
    Returns:
        The subset that failed again, and the run's return code.
    """
    if not node_ids:
        return frozenset(), 0
    argv = (python_executable(), "-m", "pytest", *node_ids, *RERUN_ARGS)
    result = run_check("confirm", argv)
    return failing_node_ids(result.output), result.returncode


def main(argv: list[str] | None = None) -> int:
    """Confirm or dismiss candidate regressions supplied as arguments or on stdin."""
    parser = argparse.ArgumentParser(description="Re-run failures to rule out flakes.")
    parser.add_argument("node_ids", nargs="*", help="pytest node ids; omit to read stdin")
    args = parser.parse_args(argv)

    node_ids = args.node_ids or [line.strip() for line in sys.stdin if line.strip()]
    if not node_ids:
        print("CONFIRM=NONE")
        return EXIT_FLAKE

    reproduced, returncode = rerun(node_ids)
    if returncode in (124, 127):
        print("CONFIRM=INFRA", file=sys.stderr)
        return EXIT_INFRA

    print(f"CONFIRM={'CONFIRMED' if reproduced else 'FLAKE'} COUNT={len(reproduced)}")
    for node_id in sorted(reproduced):
        print(f"CONFIRMED_FAILURE {node_id}")
    return EXIT_CONFIRMED if reproduced else EXIT_FLAKE


if __name__ == "__main__":
    raise SystemExit(main())
