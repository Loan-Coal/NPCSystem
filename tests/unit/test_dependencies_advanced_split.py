"""
test_dependencies_advanced_split.py - Guards the SEV-17 per-engine submodule split.

Does NOT: instantiate engines or touch infra (factories are not called here).

Dependencies injected: None.
"""

from __future__ import annotations

import importlib

import pytest

EXPECTED_FACTORIES = {
    "get_agenda_engine",
    "get_chapter_engine",
    "get_clique_formation_engine",
    "get_investigation_engine",
    "get_memory_consolidation_engine",
    "get_military_engine",
    "get_mood_contagion_engine",
    "get_need_decay_engine",
    "get_negotiation_store",
    "get_oath_engine",
    "get_skill_progression_engine",
    "get_succession_engine",
    "get_treaty_engine",
}

SUBMODULE_FACTORIES = {
    "npc_engine.api.dependencies_advanced.politics": {
        "get_treaty_engine",
        "get_oath_engine",
        "get_succession_engine",
        "get_agenda_engine",
        "get_military_engine",
    },
    "npc_engine.api.dependencies_advanced.social": {
        "get_clique_formation_engine",
        "get_mood_contagion_engine",
        "get_need_decay_engine",
        "get_negotiation_store",
    },
    "npc_engine.api.dependencies_advanced.progression": {
        "get_skill_progression_engine",
        "get_chapter_engine",
        "get_investigation_engine",
        "get_memory_consolidation_engine",
    },
}


def test_package_reexports_all_factories() -> None:
    """The dependencies_advanced package must re-export every public factory."""

    pkg = importlib.import_module("npc_engine.api.dependencies_advanced")
    for name in EXPECTED_FACTORIES:
        assert hasattr(pkg, name), f"missing re-export: {name}"
    assert set(pkg.__all__) == EXPECTED_FACTORIES


@pytest.mark.parametrize("module_name, factories", SUBMODULE_FACTORIES.items())
def test_submodule_defines_its_factories(module_name: str, factories: set[str]) -> None:
    """Each per-engine submodule must define its assigned factories."""

    module = importlib.import_module(module_name)
    for name in factories:
        assert name in module.__dict__, f"{module_name} missing {name}"


def test_submodules_partition_all_factories() -> None:
    """Every factory lives in exactly one submodule (no overlap, no orphans)."""

    seen: set[str] = set()
    for factories in SUBMODULE_FACTORIES.values():
        assert not (seen & factories), "factory defined in two submodules"
        seen |= factories
    assert seen == EXPECTED_FACTORIES
