"""
Module: tests.unit.scripts.test_check_test_quality
Layer: tests
Purpose: Unit tests for scripts/check_test_quality.py — verifies all 4 anti-vacuous
         patterns are detected and that '# quality-ok: <reason>' waivers suppress findings.
         Also pins that the real test suite flags at least the three known bad tests.
Dependencies: pathlib, sys, pytest, check_test_quality
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_test_quality import (  # noqa: E402
    BARE_EXCEPTION_RAISES,
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
# Validation pins — real suite flags the known-bad tests
# ---------------------------------------------------------------------------


def test_real_suite_flags_self_referential_retrieval_join() -> None:
    """test_retrieval_join.py::test_four_cells_sum_to_annotated_count is flagged."""
    target = _TESTS_ROOT / "unit" / "evals" / "test_retrieval_join.py"
    findings = scan_file(target)
    matching = [
        f for f in findings
        if f.pattern == SELF_REFERENTIAL_SUM
        and f.test == "test_four_cells_sum_to_annotated_count"
    ]
    assert matching, (
        "Expected SELF_REFERENTIAL_SUM finding for test_four_cells_sum_to_annotated_count"
    )


def test_real_suite_flags_vacuous_mock_deterministic_pass() -> None:
    """test_deterministic_pass.py::test_scores_every_record_without_llm is flagged."""
    target = _TESTS_ROOT / "unit" / "evals" / "test_deterministic_pass.py"
    findings = scan_file(target)
    matching = [
        f for f in findings
        if f.pattern == VACUOUS_MOCK_NOT_CALLED
        and f.test == "test_scores_every_record_without_llm"
    ]
    assert matching, (
        "Expected VACUOUS_MOCK_NOT_CALLED finding for test_scores_every_record_without_llm"
    )


def test_real_suite_flags_bare_exception_frozen_model_tests() -> None:
    """The real test suite has at least 7 pytest.raises(Exception) frozen-model tests."""
    findings = scan_directory(_TESTS_ROOT)
    bare_exception = [f for f in findings if f.pattern == BARE_EXCEPTION_RAISES]
    assert len(bare_exception) >= 7, (
        f"Expected at least 7 BARE_EXCEPTION_RAISES findings, got {len(bare_exception)}"
    )
