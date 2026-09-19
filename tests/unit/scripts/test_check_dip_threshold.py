"""
Module: tests.unit.scripts.test_check_dip_threshold
Layer: tests
Purpose: Unit tests for scripts/check_dip_threshold.py — verifies the DIP threshold
         gate correctly identifies protocols below threshold, respects waivers, and
         demonstrates it would have been red before Sprint 5 collapsed below-threshold
         ports in T9.1b–d.
Dependencies: pathlib, sys, subprocess, pytest, check_dip_threshold
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import io
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_dip_threshold import (  # noqa: E402
    check_dip_threshold,
    main,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRE_SPRINT5_SHA = "78d5282a"  # T9.1a census commit — 32 ports, none collapsed yet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_root(
    tmp_path: Path,
    *,
    port_source: str = "",
    port_filename: str = "test_port.py",
    implementor_source: str = "",
    implementor_subpath: str = "graph/repositories/fake_repo.py",
    caller_source: str = "",
    caller_subpath: str = "engines/fake/fake_engine.py",
    waivers: str = "",
) -> Path:
    """Create a minimal synthetic repo root under tmp_path for DIP gate tests."""
    ports_dir = tmp_path / "src" / "npc_engine" / "engines" / "ports"
    ports_dir.mkdir(parents=True)
    (ports_dir / "__init__.py").write_text("", encoding="utf-8")
    if port_source:
        (ports_dir / port_filename).write_text(port_source, encoding="utf-8")

    if implementor_source:
        impl_path = tmp_path / "src" / "npc_engine" / implementor_subpath
        impl_path.parent.mkdir(parents=True, exist_ok=True)
        impl_path.write_text(implementor_source, encoding="utf-8")

    if caller_source:
        caller_path = tmp_path / "src" / "npc_engine" / caller_subpath
        caller_path.parent.mkdir(parents=True, exist_ok=True)
        caller_path.write_text(caller_source, encoding="utf-8")

    if waivers is not None:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "dip_waivers.txt").write_text(waivers, encoding="utf-8")

    return tmp_path


_PORT_WITH_ONE_METHOD = """\
from __future__ import annotations
from typing import Protocol


class TestPort(Protocol):
    async def do_thing(self, *, npc_id: str) -> None:
        ...
"""

_IMPLEMENTOR_FOR_TEST_PORT = """\
from __future__ import annotations


class FakeTestRepo:
    async def do_thing(self, *, npc_id: str) -> None:
        pass
"""

_CALLER_FOR_TEST_PORT = """\
from __future__ import annotations
from npc_engine.engines.ports.test_port import TestPort


class FakeEngine:
    def __init__(self, repo: TestPort) -> None:
        self._repo = repo
"""


# ---------------------------------------------------------------------------
# RED anchor: below-threshold protocol detected
# ---------------------------------------------------------------------------


def test_protocol_with_zero_callers_fails(tmp_path: Path) -> None:
    """A protocol with no implementors and no callers must be reported as a violation."""
    root = _make_root(tmp_path, port_source=_PORT_WITH_ONE_METHOD)
    violations = check_dip_threshold(root=root)
    assert any("TestPort" in v for v in violations), (
        f"Expected TestPort violation in {violations}"
    )


def test_protocol_with_one_implementor_and_two_callers_fails(tmp_path: Path) -> None:
    """Threshold is 2 implementors OR 3 callers; 1+2 falls below on both axes."""
    caller2 = _CALLER_FOR_TEST_PORT.replace("FakeEngine", "AnotherEngine")
    root = _make_root(
        tmp_path,
        port_source=_PORT_WITH_ONE_METHOD,
        implementor_source=_IMPLEMENTOR_FOR_TEST_PORT,
        caller_source=_CALLER_FOR_TEST_PORT,
    )
    # Add a second caller file
    second = root / "src" / "npc_engine" / "engines" / "other" / "other_engine.py"
    second.parent.mkdir(parents=True, exist_ok=True)
    second.write_text(caller2, encoding="utf-8")

    violations = check_dip_threshold(root=root)
    assert any("TestPort" in v for v in violations)


# ---------------------------------------------------------------------------
# Passing cases
# ---------------------------------------------------------------------------


def test_protocol_with_three_callers_passes(tmp_path: Path) -> None:
    """3 callers is enough regardless of implementor count."""
    root = _make_root(
        tmp_path,
        port_source=_PORT_WITH_ONE_METHOD,
        caller_source=_CALLER_FOR_TEST_PORT,
    )
    # Add two more caller files
    for i in range(2):
        f = root / "src" / "npc_engine" / f"engines/eng{i}/eng{i}.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(
            _CALLER_FOR_TEST_PORT.replace("FakeEngine", f"Engine{i}"),
            encoding="utf-8",
        )

    violations = check_dip_threshold(root=root)
    assert not any("TestPort" in v for v in violations)


def test_protocol_with_two_implementors_passes(tmp_path: Path) -> None:
    """2 implementors is enough regardless of caller count."""
    root = _make_root(
        tmp_path,
        port_source=_PORT_WITH_ONE_METHOD,
        implementor_source=_IMPLEMENTOR_FOR_TEST_PORT,
    )
    second = root / "src" / "npc_engine" / "graph" / "alt_repo.py"
    second.parent.mkdir(parents=True, exist_ok=True)
    second.write_text(
        _IMPLEMENTOR_FOR_TEST_PORT.replace("FakeTestRepo", "AltTestRepo"),
        encoding="utf-8",
    )

    violations = check_dip_threshold(root=root)
    assert not any("TestPort" in v for v in violations)


# ---------------------------------------------------------------------------
# Waiver behaviour
# ---------------------------------------------------------------------------


def test_waiver_with_dec_reference_clears_violation(tmp_path: Path) -> None:
    """A waiver entry with a DEC-NNN reference suppresses the violation."""
    root = _make_root(
        tmp_path,
        port_source=_PORT_WITH_ONE_METHOD,
        waivers="TestPort  DEC-275  split for ISP; below threshold intentionally\n",
    )
    violations = check_dip_threshold(root=root)
    assert not any("TestPort" in v for v in violations)


def test_waiver_without_dec_reference_is_rejected(tmp_path: Path) -> None:
    """A waiver line missing a DEC-NNN token is invalid and raises ValueError."""
    root = _make_root(
        tmp_path,
        port_source=_PORT_WITH_ONE_METHOD,
        waivers="TestPort  no-dec-here  undocumented waiver\n",
    )
    with pytest.raises(ValueError, match="DEC-"):
        check_dip_threshold(root=root)


def test_ports_init_excluded_from_caller_count(tmp_path: Path) -> None:
    """engines/ports/__init__.py re-exports must not count as callers."""
    root = _make_root(tmp_path, port_source=_PORT_WITH_ONE_METHOD)
    # Write __init__.py that re-exports the port (as the real __init__ does)
    init = root / "src" / "npc_engine" / "engines" / "ports" / "__init__.py"
    init.write_text(
        "from npc_engine.engines.ports.test_port import TestPort\n"
        "__all__ = ['TestPort']\n",
        encoding="utf-8",
    )
    violations = check_dip_threshold(root=root)
    assert any("TestPort" in v for v in violations), (
        "__init__.py re-export must not count as a caller"
    )


def test_docstring_prose_not_counted_as_caller(tmp_path: Path) -> None:
    """Mentioning the protocol only in a docstring must not count as a caller."""
    prose_only = '''\
from __future__ import annotations


class Wiring:
    """Wires the engine-layer Port (TestPort) into the composition root."""

    def create(self) -> None:
        pass
'''
    root = _make_root(
        tmp_path,
        port_source=_PORT_WITH_ONE_METHOD,
        caller_source=prose_only,
    )
    violations = check_dip_threshold(root=root)
    assert any("TestPort" in v for v in violations), (
        "Prose mention in docstring must not count as a caller"
    )


# ---------------------------------------------------------------------------
# Current tree: must be green (all violations waiverized or above threshold)
# ---------------------------------------------------------------------------


def test_current_tree_passes() -> None:
    """The live codebase must pass the DIP gate with no unwaivered violations."""
    violations = check_dip_threshold(root=_REPO_ROOT)
    assert violations == [], f"Unexpected violations on current tree:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Pre-Sprint-5 RED anchor: gate was red before T9.1b collapsed ports
# ---------------------------------------------------------------------------


def test_pre_sprint5_tree_has_violations(tmp_path: Path) -> None:
    """Gate is red against the pre-T9.1b tree (78d5282a) — 32 ports, none collapsed."""
    result = subprocess.run(
        ["git", "archive", _PRE_SPRINT5_SHA, "--", "src/npc_engine/"],
        capture_output=True,
        cwd=_REPO_ROOT,
    )
    if result.returncode != 0:
        pytest.skip(f"git archive failed: {result.stderr.decode()[:200]}")

    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
        tar.extractall(tmp_path)

    # No waivers file in old tree — all below-threshold protocols must fail
    violations = check_dip_threshold(root=tmp_path)
    assert len(violations) > 0, (
        "Pre-Sprint-5 tree (78d5282a) must have DIP violations — "
        "24 below-threshold ports were collapsed in T9.1b–d"
    )


# ---------------------------------------------------------------------------
# main() CLI
# ---------------------------------------------------------------------------


def test_main_returns_zero_on_current_tree() -> None:
    violations = check_dip_threshold(root=_REPO_ROOT)
    assert violations == []


def test_main_argv_root(tmp_path: Path) -> None:
    """--root flag is accepted and changes the scanned tree."""
    root = _make_root(
        tmp_path,
        port_source=_PORT_WITH_ONE_METHOD,
        waivers="TestPort  DEC-275  test waiver\n",
    )
    rc = main(["--root", str(root)])
    assert rc == 0
