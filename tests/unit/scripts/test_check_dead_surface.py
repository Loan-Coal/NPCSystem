"""
Module: tests.unit.scripts.test_check_dead_surface
Layer: tests
Purpose: Unit tests for scripts/check_dead_surface.py — verifies the dead-surface gate
         finds Settings fields with no reader, dead prompt YAMLs, orphaned engine
         contracts, and graph modules with no external importer.
         Integration test (test_live_repo_has_no_dead_surface) is the final anchor:
         it passes only after the 9 dead Settings fields and 2 dead prompt YAMLs are
         deleted from the live repo.
Dependencies: pathlib, sys, pytest, check_dead_surface
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_dead_surface import (  # noqa: E402
    DeadSurfaceItem,
    check_dead_surface,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_CONFIG = """\
from __future__ import annotations
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LIVE_FIELD: str = Field(default="x")
    DEAD_FIELD: str = Field(default="y")
"""

_LIVE_CONSUMER = """\
from __future__ import annotations
from npc_engine.config import get_settings

def do_thing() -> str:
    settings = get_settings()
    return settings.LIVE_FIELD
"""


def _make_tree(
    tmp_path: Path,
    *,
    consumer_source: str = "",
    extra_prompts: dict[str, str] | None = None,
    extra_contracts: dict[str, str] | None = None,
) -> Path:
    """Build a minimal synthetic repo under tmp_path for dead-surface tests."""
    src = tmp_path / "src" / "npc_engine"
    src.mkdir(parents=True)

    # config.py with one live and one dead Settings field
    (src / "config.py").write_text(_BASE_CONFIG, encoding="utf-8")

    # Optional consumer that reads LIVE_FIELD
    if consumer_source:
        engines_dir = src / "engines" / "fake"
        engines_dir.mkdir(parents=True)
        (engines_dir / "__init__.py").write_text("", encoding="utf-8")
        (engines_dir / "fake_engine.py").write_text(consumer_source, encoding="utf-8")

    # Minimal prompts directory
    prompts_dir = src / "prompts" / "dialogue"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "system_v1.yaml").write_text(
        'system: "hello"\nuser_template: "{input}"', encoding="utf-8"
    )

    if extra_prompts:
        for rel_path, content in extra_prompts.items():
            p = src / "prompts" / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

    # Minimal contracts directory
    contracts_dir = src / "engines" / "contracts"
    contracts_dir.mkdir(parents=True)
    (contracts_dir / "dialogue_engine.yaml").write_text(
        "name: dialogue_engine\nversion: v1.0", encoding="utf-8"
    )
    # Matching engine directory
    (src / "engines" / "dialogue").mkdir(parents=True)
    (src / "engines" / "dialogue" / "__init__.py").write_text("", encoding="utf-8")

    if extra_contracts:
        for name, content in extra_contracts.items():
            (contracts_dir / name).write_text(content, encoding="utf-8")

    # Minimal graph module that IS imported externally
    graph_dir = src / "graph" / "infra"
    graph_dir.mkdir(parents=True)
    (graph_dir / "__init__.py").write_text("", encoding="utf-8")
    live_module = graph_dir / "db.py"
    live_module.write_text(
        "# graph infra db\ndef get_driver() -> None: ...\n", encoding="utf-8"
    )
    # External importer
    api_dir = src / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "__init__.py").write_text("", encoding="utf-8")
    (api_dir / "deps.py").write_text(
        "from npc_engine.graph.infra.db import get_driver\n", encoding="utf-8"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Settings field tests
# ---------------------------------------------------------------------------


class TestSettingsFields:
    """Verify dead Settings fields are found and live ones are not."""

    def test_dead_field_reported(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        items = check_dead_surface(root)
        kinds = [i.kind for i in items]
        assert "settings_field" in kinds, "dead Settings field should be reported"
        paths = [i.path for i in items if i.kind == "settings_field"]
        assert "DEAD_FIELD" in paths

    def test_live_field_not_reported(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path, consumer_source=_LIVE_CONSUMER)
        items = check_dead_surface(root)
        paths = [i.path for i in items if i.kind == "settings_field"]
        assert "LIVE_FIELD" not in paths, "live field should not be flagged"

    def test_both_dead_when_no_consumer(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        paths = [i.path for i in check_dead_surface(root) if i.kind == "settings_field"]
        assert "LIVE_FIELD" in paths
        assert "DEAD_FIELD" in paths


# ---------------------------------------------------------------------------
# Prompt YAML tests
# ---------------------------------------------------------------------------


class TestPromptYamls:
    """Verify dead prompt YAMLs are found and glob-loaded ones are not."""

    def test_explicitly_loaded_yaml_not_flagged(self, tmp_path: Path) -> None:
        # A YAML explicitly named in Python source is alive
        consumer = """\
from __future__ import annotations
from pathlib import Path
import yaml

_PROMPT = yaml.safe_load((Path(__file__).parent / "system_v1.yaml").read_text())
"""
        root = _make_tree(
            tmp_path,
            consumer_source=_LIVE_CONSUMER,
            extra_prompts={"dialogue/system_v1.yaml": "system: hello"},
        )
        # Write a consumer that names the prompt
        (root / "src" / "npc_engine" / "engines" / "fake" / "loader.py").write_text(
            consumer, encoding="utf-8"
        )
        items = check_dead_surface(root)
        paths = [i.path for i in items if i.kind == "prompt_yaml"]
        # system_v1.yaml is referenced in loader.py → should NOT be flagged
        assert not any("system_v1" in p for p in paths)

    def test_dead_prompt_reported(self, tmp_path: Path) -> None:
        root = _make_tree(
            tmp_path,
            extra_prompts={"quest_generation/slot_fill_v1.yaml": "user_template: hi"},
        )
        items = check_dead_surface(root)
        paths = [i.path for i in items if i.kind == "prompt_yaml"]
        assert any("slot_fill_v1" in p for p in paths), (
            "dead prompt yaml should be flagged"
        )

    def test_glob_loaded_yaml_not_flagged(self, tmp_path: Path) -> None:
        """Templates loaded via glob must not be flagged as dead."""
        root = _make_tree(
            tmp_path,
            extra_prompts={
                "quest_generation/templates/escort_npc.yaml": "id: escort_npc",
                "quest_generation/templates/fetch_item.yaml": "id: fetch_item",
            },
        )
        # Add a template loader that globs the directory
        loader_src = """\
from __future__ import annotations
from pathlib import Path

def load_templates(dir_path: Path) -> list:
    return [p for p in sorted(dir_path.glob("*.yaml"))]
"""
        loader_dir = root / "src" / "npc_engine" / "engines" / "quest_generation"
        loader_dir.mkdir(parents=True, exist_ok=True)
        (loader_dir / "__init__.py").write_text("", encoding="utf-8")
        (loader_dir / "template_loader.py").write_text(loader_src, encoding="utf-8")

        # Add a caller that passes the templates directory
        caller_src = """\
from __future__ import annotations
from pathlib import Path
from npc_engine.engines.quest_generation.template_loader import load_templates

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "quest_generation"

def build_engine() -> None:
    templates_dir = _PROMPTS_DIR / "templates"
    templates = load_templates(templates_dir)
"""
        api_dir = root / "src" / "npc_engine" / "api"
        api_dir.mkdir(parents=True, exist_ok=True)
        (api_dir / "deps_quest.py").write_text(caller_src, encoding="utf-8")

        items = check_dead_surface(root)
        paths = [i.path for i in items if i.kind == "prompt_yaml"]
        assert not any("escort_npc" in p for p in paths), (
            "glob-loaded escort_npc.yaml must not be flagged"
        )
        assert not any("fetch_item" in p for p in paths), (
            "glob-loaded fetch_item.yaml must not be flagged"
        )


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestContracts:
    """Verify orphaned contracts are flagged and matched ones are not."""

    def test_orphaned_contract_reported(self, tmp_path: Path) -> None:
        root = _make_tree(
            tmp_path,
            extra_contracts={
                "ghost_engine.yaml": "name: ghost_engine\nversion: v1.0"
            },
        )
        items = check_dead_surface(root)
        paths = [i.path for i in items if i.kind == "contract"]
        assert any("ghost_engine" in p for p in paths), (
            "contract with no matching engine dir should be flagged"
        )

    def test_matched_contract_not_reported(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        items = check_dead_surface(root)
        paths = [i.path for i in items if i.kind == "contract"]
        assert not any("dialogue_engine" in p for p in paths)


# ---------------------------------------------------------------------------
# Graph module tests
# ---------------------------------------------------------------------------


class TestGraphModules:
    """Verify graph modules with no external importer are flagged."""

    def test_live_graph_module_not_flagged(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        items = check_dead_surface(root)
        paths = [i.path for i in items if i.kind == "graph_module"]
        assert not any("infra/db" in p or "infra\\db" in p for p in paths)

    def test_dead_graph_module_reported(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        orphan_dir = root / "src" / "npc_engine" / "graph" / "orphan"
        orphan_dir.mkdir(parents=True)
        (orphan_dir / "__init__.py").write_text("", encoding="utf-8")
        (orphan_dir / "orphan_queries.py").write_text(
            "def query() -> None: ...\n", encoding="utf-8"
        )
        items = check_dead_surface(root)
        paths = [i.path for i in items if i.kind == "graph_module"]
        assert any("orphan_queries" in p for p in paths), (
            "graph module with no external importer should be flagged"
        )


# ---------------------------------------------------------------------------
# Integration test — RED anchor
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLiveRepo:
    """Integration tests against the actual repository tree.

    test_live_repo_has_no_dead_surface is the RED anchor: it fails until the 9 dead
    Settings fields and 2 dead prompt YAMLs are deleted from the repo. After deletion,
    all four surfaces should be clean and this test passes.
    """

    def test_live_repo_has_no_dead_surface(self) -> None:
        """Live repo reports zero dead-surface findings."""
        items = check_dead_surface(_REPO_ROOT)
        dead_fields = [i for i in items if i.kind == "settings_field"]
        dead_prompts = [i for i in items if i.kind == "prompt_yaml"]
        dead_contracts = [i for i in items if i.kind == "contract"]

        assert dead_fields == [], (
            f"Dead Settings fields: {[i.path for i in dead_fields]}"
        )
        assert dead_prompts == [], (
            f"Dead prompt YAMLs: {[i.path for i in dead_prompts]}"
        )
        assert dead_contracts == [], (
            f"Orphaned contracts: {[i.path for i in dead_contracts]}"
        )

    def test_escort_npc_not_flagged(self) -> None:
        """escort_npc.yaml and fetch_item.yaml must not be reported as dead."""
        items = check_dead_surface(_REPO_ROOT)
        paths = [i.path for i in items if i.kind == "prompt_yaml"]
        assert not any("escort_npc" in p for p in paths), (
            "escort_npc.yaml is glob-loaded and must not be flagged"
        )
        assert not any("fetch_item" in p for p in paths), (
            "fetch_item.yaml is glob-loaded and must not be flagged"
        )
