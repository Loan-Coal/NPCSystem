"""
Module: gate_baseline
Layer: harness
Purpose: Run the gate's constituent checks and snapshot the set of tests that are
    ALREADY failing, so a later red gate can be attributed to the task or to pre-existing debt.
Dependencies: scripts/loop_gates (specs), stdlib subprocess/json/argparse.
Used by: scripts/gate_attribution.py, gate_confirm.py, classify_gate_failure.py, expand_loop.sh.

Also the shared subprocess runner for every other gate script — one place that forces
UTF-8 on children (this repo's roadmap and log output is full of —, →, ✅, ⚠️, and a
cp1252 child dies with UnicodeEncodeError) and decodes defensively.

**The baseline is written at phase boundaries only, never mid-phase.** Re-seeding it
after a task would let that task launder its own regression into "pre-existing".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop_gates import (  # noqa: E402
    BASELINE_FILE,
    HALT_CHECK_SPECS,
    REPO_ROOT,
)

# pytest's short summary line: "FAILED tests/unit/x.py::test_y - AssertionError: ..."
FAILED_LINE_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)
DEFAULT_TIMEOUT_SECS = 3600
BASELINE_RUNS = 2


@dataclass(frozen=True)
class CheckResult:
    """One check's outcome: its name, exit code and combined output."""

    name: str
    returncode: int
    output: str

    @property
    def ok(self) -> bool:
        """True when the check exited cleanly."""
        return self.returncode == 0


def child_env() -> dict[str, str]:
    """Environment for gate subprocesses, with UTF-8 forced on Python children."""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_check(name: str, argv: tuple[str, ...], timeout: int = DEFAULT_TIMEOUT_SECS) -> CheckResult:
    """Run one check to completion and capture its output.

    Args:
        name: Human-readable check name, as logged and reported.
        argv: Command to execute (no shell).
        timeout: Seconds before the check is abandoned.
    Returns:
        A CheckResult; a timeout is reported as returncode 124, matching `timeout(1)`.
    """
    try:
        completed = subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            env=child_env(),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(name=name, returncode=124, output=f"TIMEOUT after {timeout}s")
    except FileNotFoundError as error:
        return CheckResult(name=name, returncode=127, output=f"NOT FOUND: {error}")
    text = completed.stdout.decode("utf-8", errors="replace")
    text += completed.stderr.decode("utf-8", errors="replace")
    return CheckResult(name=name, returncode=completed.returncode, output=text)


def failing_node_ids(output: str) -> frozenset[str]:
    """Extract pytest node ids from a run's short summary, normalising path separators."""
    return frozenset(m.group(1).replace("\\", "/") for m in FAILED_LINE_RE.finditer(output))


def collect_failures(runs: int = 1) -> tuple[frozenset[str], list[CheckResult]]:
    """Run every HALT-class check ``runs`` times and union the failing node ids.

    The union (not the intersection) is deliberate: a test that fails only
    intermittently is still pre-existing debt, and charging it to a later task would
    cost that task's phase for something it never touched.

    Args:
        runs: How many times to repeat the HALT-class checks.
    Returns:
        The union of failing node ids, and every CheckResult produced.
    """
    failures: set[str] = set()
    results: list[CheckResult] = []
    for _ in range(runs):
        for name, argv in HALT_CHECK_SPECS:
            result = run_check(name, argv)
            results.append(result)
            failures |= failing_node_ids(result.output)
    return frozenset(failures), results


def baseline_path() -> Path:
    """Absolute path of the baseline snapshot file."""
    return REPO_ROOT / BASELINE_FILE


def read_baseline() -> frozenset[str]:
    """Load the recorded already-failing node ids; empty when no snapshot exists."""
    path = baseline_path()
    if not path.exists():
        return frozenset()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return frozenset()
    return frozenset(payload.get("failing", []))


def write_baseline(failing: frozenset[str], note: str) -> Path:
    """Persist the failing set with a provenance note; returns the file path."""
    path = baseline_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"failing": sorted(failing), "note": note, "runs": BASELINE_RUNS}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """CLI: ``--write`` snapshots the current failures, ``--show`` prints the snapshot."""
    parser = argparse.ArgumentParser(description="Snapshot already-failing tests.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="run checks and record failures")
    action.add_argument("--show", action="store_true", help="print the recorded failures")
    parser.add_argument("--note", default="phase-boundary", help="provenance note for --write")
    args = parser.parse_args(argv)

    if args.show:
        for node_id in sorted(read_baseline()):
            print(node_id)
        return 0

    failing, results = collect_failures(runs=BASELINE_RUNS)
    path = write_baseline(failing, args.note)
    infra = [r for r in results if r.returncode in (124, 127)]
    for result in infra:
        print(f"BASELINE WARNING: {result.name} -> rc={result.returncode}", file=sys.stderr)
    print(f"BASELINE_WRITTEN={path} COUNT={len(failing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
