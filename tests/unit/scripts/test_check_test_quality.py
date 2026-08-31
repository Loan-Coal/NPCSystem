"""
Module: tests.unit.scripts.test_check_test_quality
Layer: tests
Purpose: Unit tests for scripts/check_test_quality.py — verifies all 4 anti-vacuous
         patterns are detected and that '# quality-ok: <reason>' waivers suppress findings.
         Also pins that the real test tree stays clean AND that its cleanliness comes from
         deliberate waivers rather than from a scanner that has stopped detecting.
Dependencies: pathlib, sys, pytest, check_test_quality
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_test_quality import (  # noqa: E402
    BARE_EXCEPTION_RAISES,
    EMPTY_TEST_BODY,
    NO_ASSERTION,
    format_findings,
    main,
    PARAMETRIZE_NO_SUT_CALL,
    SELF_REFERENTIAL_SUM,
    VACUOUS_MOCK_NOT_CALLED,
    Finding,
    scan_directory,
    scan_file,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TESTS_ROOT = _REPO_ROOT / "tests"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    """Write a synthetic Python test file and return its path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _patterns(findings: list[Finding]) -> list[str]:
    return [f.pattern for f in findings]


def _tests(findings: list[Finding]) -> list[str]:
    return [f.test for f in findings]


# ---------------------------------------------------------------------------
# RED anchor — must fail before check_test_quality.py exists
# ---------------------------------------------------------------------------


def test_self_comparing_assertion_is_flagged(tmp_path: Path) -> None:
    """Sum-of-parts == total on the same object is flagged SELF_REFERENTIAL_SUM."""
    f = _write(
        tmp_path,
        "test_example.py",
        "def test_sum_invariant():\n"
        "    assert result.a + result.b + result.c == result.total\n",
    )
    findings = scan_file(f)
    assert SELF_REFERENTIAL_SUM in _patterns(findings)


# ---------------------------------------------------------------------------
# Pattern 1: BARE_EXCEPTION_RAISES
# ---------------------------------------------------------------------------


def test_bare_exception_raises_is_flagged(tmp_path: Path) -> None:
    """pytest.raises(Exception) without a specific type is flagged."""
    f = _write(
        tmp_path,
        "test_ex.py",
        "import pytest\n"
        "def test_frozen():\n"
        "    with pytest.raises(Exception):\n"
        "        obj.field = 99\n",
    )
    findings = scan_file(f)
    assert BARE_EXCEPTION_RAISES in _patterns(findings)


def test_specific_exception_type_not_flagged(tmp_path: Path) -> None:
    """pytest.raises(ValueError) does NOT trigger BARE_EXCEPTION_RAISES."""
    f = _write(
        tmp_path,
        "test_specific.py",
        "import pytest\n"
        "def test_specific():\n"
        "    with pytest.raises(ValueError):\n"
        "        raise ValueError('oops')\n",
    )
    findings = scan_file(f)
    assert BARE_EXCEPTION_RAISES not in _patterns(findings)


# ---------------------------------------------------------------------------
# Pattern 2: SELF_REFERENTIAL_SUM — waiver
# ---------------------------------------------------------------------------


def test_self_referential_sum_waiver_suppresses_finding(tmp_path: Path) -> None:
    """A '# quality-ok:' comment on the assert line suppresses SELF_REFERENTIAL_SUM."""
    f = _write(
        tmp_path,
        "test_waived.py",
        "def test_sum_ok():\n"
        "    # quality-ok: annotated_count is an independent counter, not derived\n"
        "    assert r.a + r.b == r.total\n",
    )
    findings = scan_file(f)
    assert SELF_REFERENTIAL_SUM not in _patterns(findings)


def test_cross_object_sum_not_flagged(tmp_path: Path) -> None:
    """assert a.x + b.y == a.total (different roots on left) is NOT flagged."""
    f = _write(
        tmp_path,
        "test_cross.py",
        "def test_cross():\n"
        "    assert a.x + b.y == a.total\n",
    )
    findings = scan_file(f)
    assert SELF_REFERENTIAL_SUM not in _patterns(findings)


# ---------------------------------------------------------------------------
# Pattern 3: VACUOUS_MOCK_NOT_CALLED
# ---------------------------------------------------------------------------


def test_vacuous_mock_not_called_is_flagged(tmp_path: Path) -> None:
    """patch() + assert mock.call_count == 0 at function body level is flagged."""
    f = _write(
        tmp_path,
        "test_mock.py",
        "from unittest.mock import patch\n"
        "def test_no_llm():\n"
        "    with patch('module.func') as mock_fn:\n"
        "        do_work()\n"
        "    assert mock_fn.call_count == 0\n",
    )
    findings = scan_file(f)
    assert VACUOUS_MOCK_NOT_CALLED in _patterns(findings)


def test_assert_not_called_is_flagged(tmp_path: Path) -> None:
    """patch() + alias.assert_not_called() is also flagged."""
    f = _write(
        tmp_path,
        "test_not_called.py",
        "from unittest.mock import patch\n"
        "def test_never_called():\n"
        "    with patch('module.func') as m:\n"
        "        result = do_work()\n"
        "    m.assert_not_called()\n",
    )
    findings = scan_file(f)
    assert VACUOUS_MOCK_NOT_CALLED in _patterns(findings)


# ---------------------------------------------------------------------------
# Pattern 4: PARAMETRIZE_NO_SUT_CALL
# ---------------------------------------------------------------------------


def test_parametrize_no_call_is_flagged(tmp_path: Path) -> None:
    """Parametrized test with no function calls in body is flagged."""
    f = _write(
        tmp_path,
        "test_param.py",
        "import pytest\n"
        "@pytest.mark.parametrize('n', [1, 2, 3])\n"
        "def test_positive(n):\n"
        "    assert n > 0\n",
    )
    findings = scan_file(f)
    assert PARAMETRIZE_NO_SUT_CALL in _patterns(findings)


def test_parametrize_with_sut_call_not_flagged(tmp_path: Path) -> None:
    """Parametrized test that calls a function is NOT flagged."""
    f = _write(
        tmp_path,
        "test_param_ok.py",
        "import pytest\n"
        "@pytest.mark.parametrize('code', [200, 400, 500])\n"
        "def test_label(code):\n"
        "    assert result_label(code) == 'ok'\n",
    )
    findings = scan_file(f)
    assert PARAMETRIZE_NO_SUT_CALL not in _patterns(findings)


# ---------------------------------------------------------------------------
# Clean-file invariant
# ---------------------------------------------------------------------------


def test_clean_file_has_no_findings(tmp_path: Path) -> None:
    """A well-written test file produces no findings."""
    f = _write(
        tmp_path,
        "test_clean.py",
        "import pytest\n"
        "def test_passes():\n"
        "    result = compute(1, 2)\n"
        "    assert result == 3\n"
        "def test_raises():\n"
        "    with pytest.raises(ValueError):\n"
        "        compute(-1, -1)\n",
    )
    assert scan_file(f) == []


# ---------------------------------------------------------------------------
# Validation pins — the real tree is clean, and provably so
# ---------------------------------------------------------------------------


def test_real_suite_is_clean() -> None:
    """The real suite carries no unaddressed anti-vacuous findings.

    Replaces three earlier tests that asserted specific findings were STILL PRESENT
    (a self-referential sum in test_retrieval_join, a vacuous mock in
    test_deterministic_pass, and >=7 bare-Exception frozen-model raises). Those pinned
    the unfixed state, so they went red the moment the findings were addressed on
    2026-08-20 — a snapshot of debt cannot double as a gate. Every pattern the scanner
    detects already has synthetic coverage above; what the real tree adds is this, which
    is exactly what `make check-test-quality` enforces.

    NO_ASSERTION is excluded here and pinned separately below: it arrived in R1.8 with
    25 pre-existing findings, so it is ratcheted rather than waived. Blanket-waiving 25
    sites would buy conformance, not quality (CR-L05-03). The other five patterns keep
    the stronger zero-findings invariant they have always had.
    """
    findings = [f for f in scan_directory(_TESTS_ROOT) if f.pattern != NO_ASSERTION]

    assert findings == [], "unaddressed test-quality findings:\n" + format_findings(findings)


def test_real_suite_waivers_are_load_bearing() -> None:
    """Strip the waivers from a real file and the finding must come back.

    Without this, `test_real_suite_is_clean` would also pass if the scanner silently
    stopped detecting anything — a green gate from a broken instrument, which is the
    precise failure class this whole harness exists to catch. Proving the clean result
    is produced by deliberate waivers rather than by a no-op scanner keeps it honest.
    """
    target = _TESTS_ROOT / "unit" / "evals" / "test_deterministic_pass.py"
    assert not scan_file(target), "precondition: this file is expected to be waived clean"

    without_waivers = "\n".join(
        line for line in target.read_text(encoding="utf-8").splitlines()
        if "# quality-ok:" not in line
    )
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / target.name  # same basename so reported test ids match
        probe.write_text(without_waivers, encoding="utf-8")
        findings = scan_file(probe)

    assert any(f.pattern == VACUOUS_MOCK_NOT_CALLED for f in findings), (
        "removing the quality-ok waivers did not re-surface the VACUOUS_MOCK_NOT_CALLED "
        "finding — the scanner, not the suite, may be what is clean"
    )


# ---------------------------------------------------------------------------
# Pattern 5: EMPTY_TEST_BODY
# ---------------------------------------------------------------------------


def test_empty_test_body_is_flagged(tmp_path: Path) -> None:
    """A test function with no assertions and no calls is flagged EMPTY_TEST_BODY."""
    f = _write(tmp_path, "test_nothing.py", "def test_nothing(): pass\n")
    findings = scan_file(f)
    assert EMPTY_TEST_BODY in _patterns(findings)


def test_test_with_assertion_not_flagged_as_empty(tmp_path: Path) -> None:
    """A test with an assertion is not flagged EMPTY_TEST_BODY."""
    f = _write(
        tmp_path, "test_asserts.py",
        "def test_something():\n    assert 1 == 1\n",
    )
    findings = scan_file(f)
    assert EMPTY_TEST_BODY not in _patterns(findings)


def test_test_with_call_not_flagged_as_empty(tmp_path: Path) -> None:
    """A test that calls the SUT is NO_ASSERTION, not EMPTY_TEST_BODY — the two partition."""
    f = _write(
        tmp_path, "test_calls.py",
        "def test_something():\n    result = compute(1, 2)\n",
    )
    patterns = _patterns(scan_file(f))
    assert EMPTY_TEST_BODY not in patterns
    assert NO_ASSERTION in patterns


# ---------------------------------------------------------------------------
# Ratchet baseline: main() exit code
# ---------------------------------------------------------------------------


def test_main_exits_one_above_baseline(tmp_path: Path) -> None:
    """main() returns 1 when current findings exceed the recorded baseline."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_nothing.py").write_text("def test_nothing(): pass\n", encoding="utf-8")
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("0\n", encoding="utf-8")
    result = main(["--tests-dir", str(tests_dir), "--baseline-file", str(baseline)])
    assert result == 1


def test_main_exits_zero_at_or_below_baseline(tmp_path: Path) -> None:
    """main() returns 0 when current findings are at or below the baseline."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_nothing.py").write_text("def test_nothing(): pass\n", encoding="utf-8")
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("5\n", encoding="utf-8")
    result = main(["--tests-dir", str(tests_dir), "--baseline-file", str(baseline)])
    assert result == 0


# ---------------------------------------------------------------------------
# Pattern 6: NO_ASSERTION (R1.8 — absorbed from the deleted check_dead_tests gate)
# ---------------------------------------------------------------------------


def test_a_test_that_calls_but_never_asserts_is_flagged(tmp_path: Path) -> None:
    """The R1.8 counterfactual: exercising the SUT without checking it is a finding."""
    f = _write(tmp_path, "test_x.py", "def test_x():\n    build_thing(1)\n")
    assert NO_ASSERTION in _patterns(scan_file(f))


def test_pytest_raises_counts_as_an_assertion(tmp_path: Path) -> None:
    """pytest.raises IS the assertion — flagging it would be a false positive."""
    body = "def test_x():\n    with pytest.raises(ValueError):\n        boom()\n"
    assert NO_ASSERTION not in _patterns(scan_file(_write(tmp_path, "test_x.py", body)))


def test_a_mock_assert_method_counts_as_an_assertion(tmp_path: Path) -> None:
    body = "def test_x():\n    m.assert_called_once_with(1)\n"
    assert NO_ASSERTION not in _patterns(scan_file(_write(tmp_path, "test_x.py", body)))


def test_a_unittest_assert_method_counts_as_an_assertion(tmp_path: Path) -> None:
    body = "def test_x(self):\n    self.assertEqual(a(), 1)\n"
    assert NO_ASSERTION not in _patterns(scan_file(_write(tmp_path, "test_x.py", body)))


def test_pytest_fail_counts_as_an_assertion(tmp_path: Path) -> None:
    body = "def test_x():\n    if run():\n        pytest.fail('nope')\n"
    assert NO_ASSERTION not in _patterns(scan_file(_write(tmp_path, "test_x.py", body)))


def test_an_assertion_nested_in_a_loop_counts(tmp_path: Path) -> None:
    body = "def test_x():\n    for v in items():\n        assert v\n"
    assert NO_ASSERTION not in _patterns(scan_file(_write(tmp_path, "test_x.py", body)))


def test_a_no_assertion_finding_is_waivable(tmp_path: Path) -> None:
    """The gate shares one waiver marker with the other five patterns."""
    body = "# quality-ok: proves the call does not raise\ndef test_x():\n    build_thing(1)\n"
    assert scan_file(_write(tmp_path, "test_x.py", body)) == []


def test_a_test_is_reported_once_not_twice(tmp_path: Path) -> None:
    """EMPTY_TEST_BODY and NO_ASSERTION partition; neither test earns both labels."""
    empty = _write(tmp_path, "test_e.py", "def test_e(): pass\n")
    calls = _write(tmp_path, "test_c.py", "def test_c():\n    go()\n")
    assert _patterns(scan_file(empty)) == [EMPTY_TEST_BODY]
    assert _patterns(scan_file(calls)) == [NO_ASSERTION]


def test_real_suite_no_assertion_findings_match_the_baseline() -> None:
    """Pins the ratchet in both directions.

    Growth means an assertion-free test slipped in. Shrinkage means findings were fixed
    without re-recording, which would leave the gate looser than the tree it guards.
    """
    recorded = int(
        (_REPO_ROOT / "scripts" / "check_test_quality_baseline.txt")
        .read_text(encoding="utf-8").strip()
    )
    actual = [f for f in scan_directory(_TESTS_ROOT) if f.pattern == NO_ASSERTION]
    assert len(actual) == recorded, (
        f"{len(actual)} NO_ASSERTION findings vs baseline {recorded} — fix them, waive "
        "them with '# quality-ok: <reason>', or re-record the baseline"
    )
