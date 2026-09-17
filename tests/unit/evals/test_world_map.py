"""
Module: test_world_map
Layer: test (unit)
Purpose: Tests for evals/world_map.py — declarative scenario-to-eval-world entity
         ID mapping, unmapped-ID error raising, and completeness over the 5
         promoted scenarios.
Dependencies: pytest, world_map (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from world_map import (
    PROMOTED_SCENARIO_IDS,
    WORLD_MAP,
    UnmappedScenarioIdError,
)


def test_unmapped_scenario_id_raises() -> None:
    """An entity ID absent from the map raises UnmappedScenarioIdError."""
    with pytest.raises(UnmappedScenarioIdError):
        WORLD_MAP.resolve("scenario_gossip_chain", "nonexistent_entity_xyz")


def test_error_names_missing_entity() -> None:
    """The error message names the unmapped entity ID."""
    with pytest.raises(UnmappedScenarioIdError) as exc_info:
        WORLD_MAP.resolve("scenario_gossip_chain", "nonexistent_entity_xyz")
    assert "nonexistent_entity_xyz" in str(exc_info.value)


def test_error_names_scenario() -> None:
    """The error message names the scenario that referenced the unmapped entity."""
    with pytest.raises(UnmappedScenarioIdError) as exc_info:
        WORLD_MAP.resolve("scenario_gossip_chain", "nonexistent_entity_xyz")
    assert "scenario_gossip_chain" in str(exc_info.value)


def test_unknown_scenario_raises() -> None:
    """An entirely unknown scenario also raises UnmappedScenarioIdError."""
    with pytest.raises(UnmappedScenarioIdError):
        WORLD_MAP.resolve("scenario_does_not_exist", "npc_1")


def test_gossip_chain_entities_resolve() -> None:
    """Each entity ID in scenario_gossip_chain resolves to the correct eval-world ID."""
    assert WORLD_MAP.resolve("scenario_gossip_chain", "npc_1") == "aldric_merchant"
    assert WORLD_MAP.resolve("scenario_gossip_chain", "npc_6") == "old_henryk"
    assert WORLD_MAP.resolve("scenario_gossip_chain", "loc_market") == "loc_market_square"
    assert WORLD_MAP.resolve("scenario_gossip_chain", "player_1") == "player_demo"


def test_grief_persistence_entities_resolve() -> None:
    """Each entity ID in scenario_grief_persistence resolves correctly."""
    assert WORLD_MAP.resolve("scenario_grief_persistence", "elder_1") == "old_henryk"
    assert WORLD_MAP.resolve("scenario_grief_persistence", "player_1") == "player_demo"
    assert WORLD_MAP.resolve("scenario_grief_persistence", "loc_market") == "loc_market_square"


def test_self_seeding_scenario_raises_for_any_entity() -> None:
    """A self-seeding scenario with an empty entity map raises for any entity ID."""
    with pytest.raises(UnmappedScenarioIdError):
        WORLD_MAP.resolve("scenario_reputation_drift", "rep_test_npc")


def test_mapping_is_total_over_promoted_scenarios() -> None:
    """Every entity ID used by the promoted scenarios is covered by the map.

    Expected IDs are enumerated independently of the map — additions to a
    scenario that are not reflected in world_map.py will fail here before
    causing a silent translation miss at runtime.
    """
    expected: dict[str, set[str]] = {
        "scenario_gossip_chain": {"npc_1", "npc_6", "loc_market", "player_1"},
        "scenario_grief_persistence": {"elder_1", "player_1", "loc_market"},
        "scenario_reputation_drift": set(),
        "scenario_memory_consolidation": set(),
        "scenario_time_passage": set(),
    }

    mapped_scenario_ids = {sm.scenario_id for sm in WORLD_MAP.scenario_maps}
    assert PROMOTED_SCENARIO_IDS <= mapped_scenario_ids, (
        f"Promoted scenarios missing from map: {PROMOTED_SCENARIO_IDS - mapped_scenario_ids}"
    )

    for scenario_id, entity_ids in expected.items():
        for entity_id in entity_ids:
            resolved = WORLD_MAP.resolve(scenario_id, entity_id)
            assert resolved, (
                f"{scenario_id!r}:{entity_id!r} resolved to empty string"
            )
