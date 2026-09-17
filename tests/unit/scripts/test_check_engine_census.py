"""
Module: tests.unit.scripts.test_check_engine_census
Layer: tests
Purpose: Unit tests for scripts/check_engine_census.py — verifies that the engine
         portfolio gate catches unwired tick engines, unreachable non-tick engines,
         and unclassified directories without requiring git operations or a live stack.
Dependencies: pathlib, sys, pytest, check_engine_census
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_engine_census import (  # noqa: E402
    INFRA_EXEMPT_DIRS,
    NON_TICK_DIRS,
    TICK_DIRS,
    check_census,
    main,
)

_SCHEDULER_WITH_GOSSIP = '"gossip"\n"event"\n'
_DEPS_WITH_GOSSIP = "from npc_engine.engines.gossip.handler import GossipHandler\n"
_ROUTES_WITH_EMOTION = "from npc_engine.engines.emotion.emotion_store import EmotionStore\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_root(
    tmp_path: Path,
    engine_dirs: list[str],
    *,
    scheduler_text: str = "",
    deps_text: str = "",
    routes_text: str = "",
) -> Path:
    """Create a minimal fake repo root under tmp_path for census tests."""
    engines_dir = tmp_path / "src" / "npc_engine" / "engines"
    engines_dir.mkdir(parents=True)
    for name in engine_dirs:
        (engines_dir / name).mkdir()
        (engines_dir / name / "__init__.py").write_text("", encoding="utf-8")

    scheduler_dir = tmp_path / "src" / "npc_engine" / "scheduler"
    scheduler_dir.mkdir(parents=True)
    (scheduler_dir / "tick_scheduler.py").write_text(scheduler_text, encoding="utf-8")

    if deps_text:
        deps_dir = tmp_path / "src" / "npc_engine" / "api" / "dependencies_engines"
        deps_dir.mkdir(parents=True)
        (deps_dir / "__init__.py").write_text(deps_text, encoding="utf-8")

    if routes_text:
        routes_dir = tmp_path / "src" / "npc_engine" / "api" / "routes" / "test_r"
        routes_dir.mkdir(parents=True)
        (routes_dir / "test_route.py").write_text(routes_text, encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Classification constants
# ---------------------------------------------------------------------------


def test_infra_exempt_dirs_contains_expected() -> None:
    assert {"ports", "contracts", "llm", "tts"}.issubset(INFRA_EXEMPT_DIRS)


def test_non_tick_dirs_contains_emotion() -> None:
    assert "emotion" in NON_TICK_DIRS


def test_tick_dirs_contains_gossip_and_need() -> None:
    assert "gossip" in TICK_DIRS
    assert "need" in TICK_DIRS
    assert "planning" in TICK_DIRS


def test_tick_dirs_contains_historical_deleted_engines() -> None:
    assert {"clique", "currency", "deception", "mood", "skill"}.issubset(TICK_DIRS)


# ---------------------------------------------------------------------------
# Infra-exempt dirs are skipped
# ---------------------------------------------------------------------------


def test_infra_exempt_dir_not_reported(tmp_path: Path) -> None:
    root = _make_root(tmp_path, ["ports"], scheduler_text="")
    assert check_census(root) == []


# ---------------------------------------------------------------------------
# Tick engine checks
# ---------------------------------------------------------------------------


def test_tick_engine_with_name_in_scheduler_passes(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        ["gossip"],
        scheduler_text=_SCHEDULER_WITH_GOSSIP,
        deps_text=_DEPS_WITH_GOSSIP,
    )
    assert check_census(root) == []


def test_tick_engine_missing_from_scheduler_fails(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        ["deception"],
        scheduler_text='# no deception here\n"gossip"\n',
        deps_text="# no deception\n",
    )
    violations = check_census(root)
    assert any("deception" in v for v in violations)


def test_tick_engine_not_in_deps_fails(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        ["gossip"],
        scheduler_text=_SCHEDULER_WITH_GOSSIP,
        deps_text="# no gossip import here\n",
    )
    violations = check_census(root)
    assert any("gossip" in v for v in violations)


def test_dir_to_tick_name_mapping_need(tmp_path: Path) -> None:
    """need/ dir must satisfy the 'need_decay' tick name, not 'need'."""
    root = _make_root(
        tmp_path,
        ["need"],
        scheduler_text='"need_decay"\n',
        deps_text="from npc_engine.engines.need.need_decay_engine import NeedDecayEngine\n",
    )
    assert check_census(root) == []


def test_dir_to_tick_name_mapping_need_wrong_name_fails(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        ["need"],
        scheduler_text='"need"\n',
        deps_text="from npc_engine.engines.need.need_decay_engine import NeedDecayEngine\n",
    )
    violations = check_census(root)
    assert any("need_decay" in v for v in violations)


def test_multi_tick_name_dir_all_required(tmp_path: Path) -> None:
    """agenda/ provides both 'agenda' and 'intent_formation' — both must be present."""
    root = _make_root(
        tmp_path,
        ["agenda"],
        scheduler_text='"agenda"\n# intent_formation is absent\n',
        deps_text="from npc_engine.engines.agenda.agenda_engine import AgendaEngine\n",
    )
    violations = check_census(root)
    assert any("intent_formation" in v for v in violations)


def test_multi_tick_name_dir_all_present_passes(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        ["agenda"],
        scheduler_text='"agenda"\n"intent_formation"\n',
        deps_text="from npc_engine.engines.agenda.agenda_engine import AgendaEngine\n",
    )
    assert check_census(root) == []


# ---------------------------------------------------------------------------
# Non-tick engine checks
# ---------------------------------------------------------------------------


def test_non_tick_engine_imported_in_api_passes(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        ["emotion"],
        scheduler_text="",
        routes_text=_ROUTES_WITH_EMOTION,
    )
    assert check_census(root) == []


def test_non_tick_engine_not_imported_anywhere_fails(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        ["emotion"],
        scheduler_text="",
        routes_text="# nothing here\n",
    )
    violations = check_census(root)
    assert any("emotion" in v for v in violations)


# ---------------------------------------------------------------------------
# Unclassified directory
# ---------------------------------------------------------------------------


def test_unclassified_dir_fails_loudly(tmp_path: Path) -> None:
    """A directory not in any bucket must produce an UNCLASSIFIED violation."""
    root = _make_root(tmp_path, ["brand_new_engine"], scheduler_text="")
    violations = check_census(root)
    assert any("UNCLASSIFIED" in v for v in violations)
    assert any("brand_new_engine" in v for v in violations)


# ---------------------------------------------------------------------------
# Dunder dirs are ignored
# ---------------------------------------------------------------------------


def test_dunder_dirs_are_skipped(tmp_path: Path) -> None:
    root = _make_root(tmp_path, [], scheduler_text="")
    # Manually add __pycache__
    (tmp_path / "src" / "npc_engine" / "engines" / "__pycache__").mkdir(parents=True)
    assert check_census(root) == []


# ---------------------------------------------------------------------------
# CLI exit codes
# ---------------------------------------------------------------------------


def test_main_exits_0_on_clean_tree(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        ["gossip"],
        scheduler_text=_SCHEDULER_WITH_GOSSIP,
        deps_text=_DEPS_WITH_GOSSIP,
    )
    assert main(["--root", str(root)]) == 0


def test_main_exits_1_on_violation(tmp_path: Path) -> None:
    root = _make_root(
        tmp_path,
        ["deception"],
        scheduler_text="# nothing\n",
        deps_text="# nothing\n",
    )
    assert main(["--root", str(root)]) == 1
