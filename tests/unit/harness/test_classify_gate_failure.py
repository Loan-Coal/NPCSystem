"""Tests for ``scripts/classify_gate_failure.py`` routing, including the HARNESS bucket (T0.3).

Every HALT to date was the harness tripping over its own self-tests, and a HALT at a phase
boundary counts toward ending the night. T0.3 routes a red gate whose failures are ALL
harness self-tests — by the failing test's **path**, never by which task was running — to a
skip-and-log bucket. A mixed or product failure must still HALT; that is the half that
matters most, because a skip bucket that swallows a product failure is worse than none.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import classify_gate_failure  # noqa: E402
from gate_baseline import CheckResult  # noqa: E402

HARNESS_A = "tests/unit/scripts/test_roadmap_audit.py::test_x"
HARNESS_B = "tests/unit/harness/test_loop_gates.py::test_y"
PRODUCT = "tests/unit/api/test_routes.py::test_z"


def _pytest_output(*node_ids: str) -> str:
    summary = "".join(f"FAILED {node_id} - AssertionError\n" for node_id in node_ids)
    return f"=== short test summary info ===\n{summary}{len(node_ids)} failed\n"


def _fake_runs(monkeypatch: pytest.MonkeyPatch, tests_output: str | None) -> None:
    """Make the ``tests`` spec fail with ``tests_output`` (or pass on None); form checks pass."""

    def fake_run_check(name: str, argv: tuple[str, ...]) -> CheckResult:
        failed = name == "tests" and tests_output is not None
        return CheckResult(name=name, returncode=int(failed), output=tests_output or "")

    monkeypatch.setattr(classify_gate_failure, "run_check", fake_run_check)


@pytest.mark.parametrize(
    ("failing", "expected_code", "expected_class"),
    [
        ((HARNESS_A,), classify_gate_failure.EXIT_HARNESS, "HARNESS"),
        ((HARNESS_A, HARNESS_B), classify_gate_failure.EXIT_HARNESS, "HARNESS"),
        ((HARNESS_A, PRODUCT), classify_gate_failure.EXIT_HALT, "HALT"),
        ((PRODUCT,), classify_gate_failure.EXIT_HALT, "HALT"),
    ],
)
def test_red_tests_route_by_failing_test_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failing: tuple[str, ...],
    expected_code: int,
    expected_class: str,
) -> None:
    _fake_runs(monkeypatch, _pytest_output(*failing))
    assert classify_gate_failure.main(["--quiet"]) == expected_code
    assert f"CLASSIFICATION={expected_class} " in capsys.readouterr().out


def test_windows_separators_still_route_to_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_runs(monkeypatch, _pytest_output(HARNESS_A.replace("/", "\\")))
    assert classify_gate_failure.main(["--quiet"]) == classify_gate_failure.EXIT_HARNESS


def test_red_tests_with_no_parseable_failure_still_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    """A crashed run names no node at all — "all failures are harness" must not be vacuous."""
    _fake_runs(monkeypatch, "INTERNALERROR> Traceback (most recent call last):\n")
    assert classify_gate_failure.main(["--quiet"]) == classify_gate_failure.EXIT_HALT


def test_a_test_elsewhere_whose_name_mentions_harness_still_halts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefix match on the path, not a substring — tests/unit/api/harness_x is a product test."""
    _fake_runs(monkeypatch, _pytest_output("tests/unit/api/test_harness_scripts.py::test_q"))
    assert classify_gate_failure.main(["--quiet"]) == classify_gate_failure.EXIT_HALT
