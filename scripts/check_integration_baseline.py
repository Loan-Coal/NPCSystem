#!/usr/bin/env python
"""
Module: check_integration_baseline
Layer: harness (repo-level dev tool)
Purpose: Ratchet the integration suite against a committed allowlist of known-failing
         pytest node ids, so a NEW integration failure reds while pre-existing debt does not.
Dependencies: stdlib + pytest (already a dev dependency).
Used by: `make check-integration-baseline`, the CI integration job.

Why a node-id allowlist and not a count (R2.2, DEC-236's reasoning applied again):
a count-based ratchet passes when one test is fixed and a different one breaks in the same
run. Every other ratchet in this repo stores an integer because its subject is a population
of violations; here the subject is a *named set*, and the names are stable. This mirrors
`check_rules.py`, the repo's only other set-based ratchet, including its policy that a
resolved entry prints a nag and exits 0 rather than failing the build.

Why it also asserts an executed-count floor: the integration tests gate themselves with
`_skip_if_no_neo4j()`, which calls `pytest.skip()` at runtime. A job with missing or wrong
NEO4J_* env vars therefore passes green with every graph test skipped — indistinguishable
from success, and the exact vacuity R2.2 exists to remove. "Nothing failed" is not evidence
the suite ran.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / "scripts" / "integration_baseline.txt"
INTEGRATION_PATH = "tests/integration"

# Minimum tests that must actually execute (pass or fail) for the run to count as real.
# Measured 2026-09-21 on the eval-stack Neo4j after T11.3: 107 executed. Without NEO4J_* set,
# only 9 execute. A floor of 100 fails an all-skip run, and also a partial one that silently
# skips T11.3's 56 repository tests, while leaving headroom below the 107 that really run.
MIN_EXECUTED_TESTS = 100

# pytest's short-summary lines: "FAILED path::test - reason" / "ERROR path::test".
_FAILED_LINE_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)
# The terminal counts line, e.g. "8 failed, 26 passed, 9 skipped in 41.02s".
_COUNT_RE = re.compile(r"(\d+) (passed|failed|error|errors)")

_BASELINE_HEADER = (
    "# Known-failing integration tests, by pytest node id (R2.2).\n"
    "# The gate fails only on a node id that is NOT in this list. Shrink this file as R3.6\n"
    "# fixes them (run `make check-integration-baseline-update`). Never add a line by hand\n"
    "# to dodge the gate — a new failure here is a regression, not debt.\n"
)


def failing_node_ids(output: str) -> frozenset[str]:
    """Extract pytest node ids from a run's short summary, normalising path separators.

    Args:
        output: Combined stdout+stderr of a pytest run invoked with `-rf`.
    Returns:
        The set of node ids reported as FAILED or ERROR.
    """
    return frozenset(m.group(1).replace("\\", "/") for m in _FAILED_LINE_RE.finditer(output))


def executed_count(output: str) -> int:
    """Return how many tests actually ran (passed + failed + errored), excluding skips."""
    return sum(int(n) for n, word in _COUNT_RE.findall(output) if word != "skipped")


def load_baseline(path: Path = BASELINE_PATH) -> set[str]:
    """Load the allowlisted node ids (comments and blank lines ignored)."""
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def write_baseline(node_ids: set[str], path: Path = BASELINE_PATH) -> None:
    """Persist the allowlist, sorted, with a self-documenting header."""
    body = "\n".join(sorted(node_ids))
    path.write_text(_BASELINE_HEADER + body + ("\n" if body else ""), encoding="utf-8")


def run_integration_suite() -> str:
    """Run the integration suite and return its combined output."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", INTEGRATION_PATH, "-q", "--tb=no", "-rf",
         "-p", "no:cacheprovider"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def _report_vacuous_run(executed: int, label: str) -> None:
    """Explain that the suite skipped rather than ran, and how to fix it."""
    print(
        f"{label}: FAIL - only {executed} test(s) executed, expected at least "
        f"{MIN_EXECUTED_TESTS}. The suite skipped instead of running: check that "
        f"NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD are set and bolt is reachable. "
        f"A green run over an all-skip suite is the vacuity this gate exists to catch."
    )


def _report_resolved(resolved: set[str], label: str) -> None:
    """Nag (but do not fail) when a known-failing test starts passing."""
    print(
        f"{label}: {len(resolved)} baselined failure(s) now passing - run "
        f"`make check-integration-baseline-update` to ratchet down:"
    )
    for node_id in sorted(resolved):
        print(f"  + {node_id}")


def _report_new(new: set[str], label: str) -> None:
    """Name every failure that is not on the allowlist."""
    print(f"{label}: FAIL - {len(new)} NEW integration failure(s):")
    for node_id in sorted(new):
        print(f"  - {node_id}")
    print()
    print(
        "These are regressions, not pre-existing debt. Fix them, or if one is "
        "genuinely pre-existing, say so in the commit and re-baseline deliberately."
    )


def evaluate(output: str, baseline: set[str], label: str = "check-integration-baseline") -> int:
    """Compare a run's failures against the allowlist and report.

    Args:
        output: Combined pytest output.
        baseline: Allowlisted node ids.
        label: Prefix for printed messages.
    Returns:
        0 when no unlisted failure occurred and the suite really ran; 1 otherwise.
    """
    executed = executed_count(output)
    if executed < MIN_EXECUTED_TESTS:
        _report_vacuous_run(executed, label)
        return 1

    current = failing_node_ids(output)
    new = current - baseline
    resolved = baseline - current

    if resolved:
        _report_resolved(resolved, label)
    if new:
        _report_new(new, label)
        return 1

    print(f"{label}: OK - {executed} executed, no new failures ({len(baseline)} known-failing).")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the integration ratchet. Exit 1 on a new failure or a vacuous run."""
    parser = argparse.ArgumentParser(
        description="Ratchet the integration suite against a known-failing allowlist."
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Record the current failures as the new allowlist.",
    )
    args = parser.parse_args(argv)

    output = run_integration_suite()

    if args.update_baseline:
        executed = executed_count(output)
        if executed < MIN_EXECUTED_TESTS:
            sys.stderr.write(output)
            print(
                f"check-integration-baseline: REFUSING to record a baseline from a run "
                f"that executed only {executed} test(s) (expected >= {MIN_EXECUTED_TESTS}). "
                f"Recording an all-skip run would erase the allowlist."
            )
            return 1
        current = failing_node_ids(output)
        write_baseline(set(current))
        print(f"check-integration-baseline: baseline set to {len(current)} known-failing test(s).")
        return 0

    return evaluate(output, load_baseline())


if __name__ == "__main__":
    raise SystemExit(main())
