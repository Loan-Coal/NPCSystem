"""
Module: tests.unit.conformance.test_python_target_consistency
Layer: tests
Purpose: One declared Python target across the repo (R5.2, CR-L16-06). CI, the type
         checker, the package metadata and the container image must agree.
Dependencies: pathlib, re, tomllib
Used by: make test (pytest discovery), make check via test-cov

Why this exists: measured at R5.2, CI ran 3.14 across six jobs and the local venv was
3.14.2, while Dockerfile said python:3.11-slim, mypy.ini said python_version = 3.11 and
pyproject said requires-python >= 3.11. Nothing reconciled them, so mypy was type-checking
against a language version the code never runs on and the container ran a different
interpreter from CI. Static parse only — no subprocess, no Docker.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_MYPY_INI = _REPO_ROOT / "mypy.ini"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_DOCKERFILE = _REPO_ROOT / "Dockerfile"

_VERSION = r"(\d+\.\d+)"


def _ci_python_versions() -> set[str]:
    """Return every python-version pinned by the CI workflow."""
    text = _CI_WORKFLOW.read_text(encoding="utf-8")
    return set(re.findall(rf'python-version:\s*"?{_VERSION}"?', text))


def _mypy_python_version() -> str:
    """Return the language version mypy is configured to check against."""
    match = re.search(rf"^python_version\s*=\s*{_VERSION}", _MYPY_INI.read_text(encoding="utf-8"), re.M)
    assert match is not None, "mypy.ini declares no python_version"
    return match.group(1)


def _requires_python_floor() -> str:
    """Return the minimum version pyproject's requires-python allows."""
    config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    requires = str(config["project"]["requires-python"])
    match = re.search(rf">=\s*{_VERSION}", requires)
    assert match is not None, f"requires-python has no >= floor: {requires!r}"
    return match.group(1)


def _dockerfile_python_version() -> str:
    """Return the Python version of the container base image."""
    match = re.search(rf"^FROM\s+python:{_VERSION}", _DOCKERFILE.read_text(encoding="utf-8"), re.M)
    assert match is not None, "Dockerfile does not build FROM a python: base image"
    return match.group(1)


def test_one_declared_python_target() -> None:
    ci = _ci_python_versions()
    assert len(ci) == 1, f"CI pins more than one python-version: {sorted(ci)}"
    declared = {
        "ci.yml": ci.pop(),
        "mypy.ini": _mypy_python_version(),
        "pyproject.toml requires-python": _requires_python_floor(),
        "Dockerfile": _dockerfile_python_version(),
    }
    assert len(set(declared.values())) == 1, (
        "the repo declares more than one Python target:\n"
        + "\n".join(f"  {where}: {version}" for where, version in sorted(declared.items()))
    )
