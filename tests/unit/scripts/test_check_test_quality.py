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
    format_findings,
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
    """
    findings = scan_directory(_TESTS_ROOT)

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
