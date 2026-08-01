"""Tests for the overnight loop's gate decomposition, attribution and gaming scanner.

The scanner is the piece that must not have false negatives: it is the only thing
standing between a bounded repair session and a gate that goes green having fixed
nothing. `scripts/rules_baseline.txt` is the repo-specific trap — `make
check-rules-update` legitimately rewrites it, so a repair that runs the update target
launders every new violation into "expected".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from gate_attribution import new_failures  # noqa: E402
from gate_baseline import failing_node_ids  # noqa: E402
from loop_gates import (  # noqa: E402
    AUTOFIX_CHECK_SPECS,
    FROZEN_PATH_PREFIXES,
    HALT_CHECK_SPECS,
)
from scan_fix_diff import scan  # noqa: E402


def _diff(path: str, *added: str) -> str:
    body = "".join(f"+{line}\n" for line in added)
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n{body}"


# --- failing-test parsing -----------------------------------------------------------


def test_failing_node_ids_parses_pytest_short_summary() -> None:
    output = (
        "=== short test summary info ===\n"
        "FAILED tests/unit/api/test_x.py::test_a - AssertionError: nope\n"
        "ERROR tests/unit/graph/test_y.py::test_b\n"
        "2 failed, 10 passed\n"
    )
    assert failing_node_ids(output) == {
        "tests/unit/api/test_x.py::test_a",
        "tests/unit/graph/test_y.py::test_b",
    }


def test_failing_node_ids_normalises_windows_separators() -> None:
    assert failing_node_ids("FAILED tests\\unit\\test_x.py::test_a - boom\n") == {
        "tests/unit/test_x.py::test_a"
    }


def test_failing_node_ids_empty_on_a_green_run() -> None:
    assert failing_node_ids("2618 passed, 29 skipped in 92.10s\n") == frozenset()


# --- attribution --------------------------------------------------------------------


def test_pre_existing_failure_is_not_charged_to_the_task() -> None:
    baseline = frozenset({"tests/unit/test_x.py::test_a"})
    assert new_failures(baseline, baseline) == frozenset()


def test_a_genuinely_new_failure_is_surfaced() -> None:
    baseline = frozenset({"tests/unit/test_x.py::test_a"})
    current = baseline | {"tests/unit/test_y.py::test_b"}
    assert new_failures(current, baseline) == {"tests/unit/test_y.py::test_b"}


# --- gate-gaming scanner ------------------------------------------------------------


def test_rules_baseline_is_frozen() -> None:
    assert "scripts/rules_baseline.txt" in FROZEN_PATH_PREFIXES
    findings = scan(_diff("scripts/rules_baseline.txt", "src/npc_engine/x.py:12 SEV-01"))
    assert any(f.rule == "frozen-path" for f in findings)


def test_editing_a_test_file_is_flagged() -> None:
    findings = scan(_diff("tests/unit/api/test_x.py", "    assert True"))
    assert any(f.rule == "frozen-path" for f in findings)


def test_editing_the_makefile_is_flagged() -> None:
    assert any(f.rule == "frozen-path" for f in scan(_diff("Makefile", "check: lint")))


@pytest.mark.parametrize(
    ("added", "rule"),
    [
        ("x = 1  # noqa", "noqa"),
        ("y = cast(int, z)  # type: ignore[arg-type]", "type-ignore"),
        ("    except ValueError: pass", "swallowed-except"),
        ("    except:", "bare-except"),
        ("@pytest.mark.skip(reason='later')", "skip-marker"),
        ("        pytest.skip('no neo4j')", "runtime-skip"),
        ("\t--cov-fail-under=50 \\", "coverage-threshold"),
        ("ignore_errors = True", "mypy-silence"),
    ],
)
def test_suppression_patterns_are_detected(added: str, rule: str) -> None:
    findings = scan(_diff("src/npc_engine/engines/x.py", added))
    assert rule in {f.rule for f in findings}, f"{rule} not detected in {added!r}"


def test_a_genuine_repair_scans_clean() -> None:
    diff = _diff(
        "src/npc_engine/engines/dialogue/prompt_builder.py",
        "from __future__ import annotations",
        "",
        "MAX_TURNS: int = 12",
        "def build(turns: list[str]) -> str:",
        '    """Build the prompt."""',
        "    return chr(10).join(turns[:MAX_TURNS])",
    )
    assert scan(diff) == []


def test_scanner_attributes_a_finding_to_the_right_file() -> None:
    diff = _diff("src/npc_engine/a.py", "ok = 1") + _diff("src/npc_engine/b.py", "bad = 1  # noqa")
    findings = [f for f in scan(diff) if f.rule == "noqa"]
    assert len(findings) == 1
    assert findings[0].path == "src/npc_engine/b.py"


# --- spec sanity --------------------------------------------------------------------


def test_halt_specs_run_tests_and_autofix_specs_do_not() -> None:
    halt_names = {name for name, _ in HALT_CHECK_SPECS}
    autofix_names = {name for name, _ in AUTOFIX_CHECK_SPECS}
    assert "tests" in halt_names
    assert not halt_names & autofix_names
    assert {"lint", "type", "check-rules", "check-layers"} <= autofix_names


def test_autofix_specs_delegate_to_make_so_they_track_gate_edits() -> None:
    # EVAL-P0.3 widens `lint`; EVAL-P6.3 rewrites seven targets. Naming ruff/mypy
    # directly here would silently drift out of step the moment those tasks land.
    assert all(argv[0] == "make" for _, argv in AUTOFIX_CHECK_SPECS)
