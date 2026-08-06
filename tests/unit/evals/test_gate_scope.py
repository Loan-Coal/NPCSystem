"""
Module: test_gate_scope
Layer: test (unit)
Purpose: Mechanically enforce the EVAL-P0.3 gate scope — the Makefile `lint` recipe must
         name `evals/` as well as `src/`, and the canonical `check` gate must depend on it.
Dependencies: pathlib, re
Used by: pytest (make test / make check)

Why this exists: evals/ carried lint debt invisibly for months because `make lint` only ever
named src/. A scope claim that no test enforces silently decays the next time someone edits
the recipe; this parses the Makefile so the regression fails loudly.

Static parse only — no subprocess, no ruff invocation (DEC: unit tests do no I/O beyond
reading the repo file under test).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_harness_honesty import _LINT_PATHS  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MAKEFILE = _REPO_ROOT / "Makefile"
_LINT_TARGET = "lint"
_CHECK_TARGET = "check"
_REQUIRED_LINT_PATHS = ("src/", "evals/")


def read_makefile() -> str:
    """Return the repo Makefile source text."""
    return _MAKEFILE.read_text(encoding="utf-8")


def recipe_lines(makefile: str, target: str) -> list[str]:
    """Return the tab-indented recipe lines of one Makefile target.

    Args:
        makefile: Full Makefile source text.
        target: Target name to look up (without the trailing colon).

    Returns:
        The recipe body lines, tabs stripped; empty when the target has no recipe.

    Raises:
        AssertionError: When the target is not declared in the Makefile.
    """
    lines = makefile.splitlines()
    start = _target_index(lines, target)
    assert start is not None, f"target '{target}:' not found in Makefile"
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("\t"):
            body.append(line[1:])
        elif line.strip() == "" or line.lstrip().startswith("#"):
            continue
        else:
            break
    return body


def prerequisites(makefile: str, target: str) -> list[str]:
    """Return the prerequisite names declared on a Makefile target line."""
    lines = makefile.splitlines()
    start = _target_index(lines, target)
    assert start is not None, f"target '{target}:' not found in Makefile"
    return lines[start].split(":", 1)[1].split()


def _target_index(lines: list[str], target: str) -> int | None:
    pattern = re.compile(rf"^{re.escape(target)}\s*:(?!=)")
    for index, line in enumerate(lines):
        if pattern.match(line):
            return index
    return None


# ── parser self-tests ──────────────────────────────────────────────────────────

_FAKE_MAKEFILE = "\n".join(
    [
        "lint:",
        "\t$(PYTHON) -m ruff check src/ evals/",
        "",
        "type:",
        "\t$(PYTHON) -m mypy src/",
        "",
        "check: lint type test-cov",
        "",
    ]
)


def test_parser_extracts_recipe_body() -> None:
    assert recipe_lines(_FAKE_MAKEFILE, "lint") == ["$(PYTHON) -m ruff check src/ evals/"]


def test_parser_stops_at_next_target() -> None:
    assert recipe_lines(_FAKE_MAKEFILE, "type") == ["$(PYTHON) -m mypy src/"]


def test_parser_extracts_prerequisites() -> None:
    assert prerequisites(_FAKE_MAKEFILE, "check") == ["lint", "type", "test-cov"]


# ── guard the guard ────────────────────────────────────────────────────────────


def test_evals_directory_holds_python_modules() -> None:
    """A lint-scope claim over an empty directory would pass vacuously."""
    modules = sorted(p.name for p in (_REPO_ROOT / "evals").glob("*.py"))
    assert "runner.py" in modules, f"evals/ has no runner.py — scope claim is meaningless: {modules}"


# ── the real scope assertions ──────────────────────────────────────────────────


def test_lint_target_covers_evals() -> None:
    """`make lint` must run ruff over evals/ as well as src/ (EVAL-P0.3)."""
    recipe = " ".join(recipe_lines(read_makefile(), _LINT_TARGET))
    missing = [path for path in _REQUIRED_LINT_PATHS if path not in recipe]
    assert not missing, f"lint recipe does not cover {missing}: {recipe!r}"


def test_check_gate_depends_on_lint() -> None:
    """The canonical health gate must actually run the lint target."""
    assert _LINT_TARGET in prerequisites(read_makefile(), _CHECK_TARGET)


def test_harness_honesty_lint_scope_matches_the_makefile() -> None:
    """`check_harness_honesty` re-runs ruff itself — a narrower scope would exempt evals/.

    That script's whole job is catching the harness claiming a gate is green when it is
    not, so its own ruff invocation drifting from the `lint` recipe is the worst possible
    place for the two to disagree.
    """
    recipe = " ".join(recipe_lines(read_makefile(), _LINT_TARGET))
    missing = [path for path in _LINT_PATHS if path not in recipe]
    assert not missing, f"check_harness_honesty lints {missing} that `make lint` does not"
    unchecked = [path for path in _REQUIRED_LINT_PATHS if path not in _LINT_PATHS]
    assert not unchecked, f"`make lint` covers {unchecked} but check_harness_honesty does not"
