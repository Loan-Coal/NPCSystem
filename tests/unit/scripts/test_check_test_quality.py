"""
Module: tests.unit.scripts.test_check_test_quality
Layer: tests
Purpose: Unit tests for scripts/check_test_quality.py — verifies all 8 anti-vacuous
         patterns are detected. The '# quality-ok:' waiver mechanism was removed in T12.1
         (Rule 5: a test must be able to fail with no waiver clause). Also pins that the
         real test tree stays clean and that its cleanliness comes from real fixes,
         not from a scanner that has stopped detecting.
Dependencies: pathlib, sys, pytest, check_test_quality
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_test_quality import (  # noqa: E402
    BARE_EXCEPTION_RAISES,
    CONSTANT_EQ_LITERAL,
    EMPTY_TEST_BODY,
    EXISTENCE_ONLY_ASSERTION,
    NO_ASSERTION,
    PARAMETRIZE_NO_SUT_CALL,
    SELF_REFERENTIAL_SUM,
    VACUOUS_MOCK_NOT_CALLED,
    Finding,
    format_findings,
    main,
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
# Pattern 2: SELF_REFERENTIAL_SUM
# ---------------------------------------------------------------------------


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


def test_not_called_attribute_forms_are_flagged(tmp_path: Path) -> None:
    """`assert not m.called` and `assert m.called is False` are the same claim — both flagged."""
    f = _write(
        tmp_path,
        "test_not_called_attr.py",
        "from unittest.mock import patch\n"
        "def test_a():\n"
        "    with patch('module.func') as m:\n"
        "        do_work()\n"
        "    assert not m.called\n"
        "def test_b():\n"
        "    with patch('module.func') as m:\n"
        "        do_work()\n"
        "    assert m.called is False\n",
    )
    assert _patterns(scan_file(f)).count(VACUOUS_MOCK_NOT_CALLED) == 2


def test_not_called_is_real_when_a_sibling_proves_the_target_is_reached(tmp_path: Path) -> None:
    """A sibling asserting the same patch target IS called makes "not called" a real claim."""
    f = _write(
        tmp_path,
        "test_sibling.py",
        "from unittest.mock import patch\n"
        "def test_skip_path():\n"
        "    with patch('module.func') as m:\n"
        "        do_work(skip=True)\n"
        "    assert not m.called\n"
        "def test_normal_path():\n"
        "    with patch('module.func') as m:\n"
        "        do_work(skip=False)\n"
        "    m.assert_called_once()\n",
    )
    assert VACUOUS_MOCK_NOT_CALLED not in _patterns(scan_file(f))


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
# Validation pins — the real tree is clean
# ---------------------------------------------------------------------------


def test_real_suite_is_clean() -> None:
    """The real suite carries no unaddressed anti-vacuous findings.

    All eight patterns are enforced at zero — waivers were removed in T12.1.
    This replaces the earlier test that excluded NO_ASSERTION from the invariant;
    after T11.1a-c cleared all prior findings, the zero invariant applies to all.
    """
    findings = scan_directory(_TESTS_ROOT)
    assert findings == [], "unaddressed test-quality findings:\n" + format_findings(findings)


def test_real_suite_clean_result_comes_from_proven_reachability() -> None:
    """Remove a real file's sibling proof and its not-called finding must come back.

    Without this, test_real_suite_is_clean would also pass if the scanner silently
    stopped detecting anything — a green gate from a broken instrument. The real
    test_judge_runner.py is clean only because a sibling test asserts the patched
    judge IS called; keeping just the not-called test must re-surface the finding.
    """
    target = _TESTS_ROOT / "unit" / "test_judge_runner.py"
    assert not scan_file(target), "precondition: this file is expected to be clean"

    tree = ast.parse(target.read_text(encoding="utf-8"))
    tree.body = [
        node for node in tree.body
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        or node.name == "test_judge_kind_none_is_skipped"
    ]
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / target.name
        probe.write_text(ast.unparse(tree), encoding="utf-8")
        findings = scan_file(probe)

    assert VACUOUS_MOCK_NOT_CALLED in _patterns(findings), (
        "removing the sibling reachability proof did not re-surface the finding "
        "— the scanner, not the suite, may be what is clean"
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
# Pattern 6: NO_ASSERTION (R1.8)
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
    """mock.assert_called_once_with(...) counts as an assertion."""
    body = "def test_x():\n    m.assert_called_once_with(1)\n"
    assert NO_ASSERTION not in _patterns(scan_file(_write(tmp_path, "test_x.py", body)))


def test_a_unittest_assert_method_counts_as_an_assertion(tmp_path: Path) -> None:
    """self.assertEqual counts as an assertion."""
    body = "def test_x(self):\n    self.assertEqual(a(), 1)\n"
    assert NO_ASSERTION not in _patterns(scan_file(_write(tmp_path, "test_x.py", body)))


def test_pytest_fail_counts_as_an_assertion(tmp_path: Path) -> None:
    """pytest.fail() counts as an assertion."""
    body = "def test_x():\n    if run():\n        pytest.fail('nope')\n"
    assert NO_ASSERTION not in _patterns(scan_file(_write(tmp_path, "test_x.py", body)))


def test_an_assertion_nested_in_a_loop_counts(tmp_path: Path) -> None:
    """An assertion inside a for loop counts."""
    body = "def test_x():\n    for v in items():\n        assert v\n"
    assert NO_ASSERTION not in _patterns(scan_file(_write(tmp_path, "test_x.py", body)))


def test_a_test_is_reported_once_not_twice(tmp_path: Path) -> None:
    """EMPTY_TEST_BODY and NO_ASSERTION partition; neither test earns both labels."""
    empty = _write(tmp_path, "test_e.py", "def test_e(): pass\n")
    calls = _write(tmp_path, "test_c.py", "def test_c():\n    go()\n")
    assert _patterns(scan_file(empty)) == [EMPTY_TEST_BODY]
    assert _patterns(scan_file(calls)) == [NO_ASSERTION]


# ---------------------------------------------------------------------------
# Pattern 7: EXISTENCE_ONLY_ASSERTION (T12.1, Rule 5)
# ---------------------------------------------------------------------------


def test_hasattr_assertion_is_flagged(tmp_path: Path) -> None:
    """assert hasattr(obj, 'attr') is flagged as EXISTENCE_ONLY_ASSERTION."""
    f = _write(
        tmp_path,
        "test_hasattr.py",
        "def test_module_attr():\n"
        "    assert hasattr(pkg, 'factory')\n",
    )
    findings = scan_file(f)
    assert EXISTENCE_ONLY_ASSERTION in _patterns(findings)


def test_iscoroutinefunction_assertion_is_flagged(tmp_path: Path) -> None:
    """assert iscoroutinefunction(fn) is flagged as EXISTENCE_ONLY_ASSERTION."""
    f = _write(
        tmp_path,
        "test_coro.py",
        "from inspect import iscoroutinefunction\n"
        "def test_is_async():\n"
        "    assert iscoroutinefunction(my_func)\n",
    )
    findings = scan_file(f)
    assert EXISTENCE_ONLY_ASSERTION in _patterns(findings)


def test_module_qualified_iscoroutinefunction_is_flagged(tmp_path: Path) -> None:
    """assert inspect.iscoroutinefunction(fn) is the same existence check — flagged."""
    f = _write(
        tmp_path,
        "test_coro_qualified.py",
        "import inspect\n"
        "def test_is_async():\n"
        "    assert inspect.iscoroutinefunction(my_func)\n",
    )
    assert EXISTENCE_ONLY_ASSERTION in _patterns(scan_file(f))


def test_callable_check_not_flagged_as_existence_only(tmp_path: Path) -> None:
    """assert callable(getattr(pkg, name)) is NOT flagged (checks a value, not existence)."""
    f = _write(
        tmp_path,
        "test_callable.py",
        "def test_factory_is_callable():\n"
        "    assert callable(getattr(pkg, 'factory'))\n",
    )
    findings = scan_file(f)
    assert EXISTENCE_ONLY_ASSERTION not in _patterns(findings)


def test_value_assertion_after_hasattr_pattern_not_double_flagged(tmp_path: Path) -> None:
    """A function with assert hasattr(...) gets EXISTENCE_ONLY, not also flagged for other issues."""
    f = _write(
        tmp_path,
        "test_mixed.py",
        "def test_has_attr_and_value():\n"
        "    assert hasattr(pkg, 'factory')\n"
        "    assert pkg.factory() is not None\n",
    )
    patterns = _patterns(scan_file(f))
    assert EXISTENCE_ONLY_ASSERTION in patterns
    assert EMPTY_TEST_BODY not in patterns
    assert NO_ASSERTION not in patterns


# ---------------------------------------------------------------------------
# Pattern 8: CONSTANT_EQ_LITERAL (T12.1, Rule 5)
# ---------------------------------------------------------------------------


def test_constant_equals_constant_is_flagged(tmp_path: Path) -> None:
    """assert 1 == 1 is flagged as CONSTANT_EQ_LITERAL."""
    f = _write(
        tmp_path,
        "test_const.py",
        "def test_trivial():\n"
        "    assert 1 == 1\n",
    )
    findings = scan_file(f)
    assert CONSTANT_EQ_LITERAL in _patterns(findings)


def test_string_constant_eq_literal_is_flagged(tmp_path: Path) -> None:
    """assert 'foo' == 'foo' is flagged as CONSTANT_EQ_LITERAL."""
    f = _write(
        tmp_path,
        "test_strconst.py",
        "def test_string_identity():\n"
        "    assert 'status' == 'status'\n",
    )
    findings = scan_file(f)
    assert CONSTANT_EQ_LITERAL in _patterns(findings)


def test_module_constant_eq_literal_is_flagged(tmp_path: Path) -> None:
    """assert MAX_CHARS == 1000 restates the source — flagged; settings.MAX_CHARS is not."""
    f = _write(
        tmp_path,
        "test_module_const.py",
        "def test_pin():\n"
        "    assert MAX_CHARS == 1000\n"
        "def test_setting():\n"
        "    assert settings.MAX_CHARS == 1000\n",
    )
    findings = scan_file(f)
    assert [x.test for x in findings if x.pattern == CONSTANT_EQ_LITERAL] == ["test_pin"]


def test_variable_compared_to_constant_not_flagged(tmp_path: Path) -> None:
    """assert result == 'ok' is NOT flagged (left side is a variable)."""
    f = _write(
        tmp_path,
        "test_var.py",
        "def test_result():\n"
        "    assert result == 'ok'\n",
    )
    findings = scan_file(f)
    assert CONSTANT_EQ_LITERAL not in _patterns(findings)
