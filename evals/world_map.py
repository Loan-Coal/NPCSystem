"""
Module: world_map
Layer: evals (eval harness — standalone, outside npc_engine layer model)
Purpose: Declarative mapping from e2e scenario entity IDs to seeded eval-world IDs.
         One measured scenario can reference entities by the generic IDs the scenario
         uses (e.g. npc_1, loc_market) and resolve them to canonical eval-world IDs
         (e.g. aldric_merchant, loc_market_square) at runtime.
         An unmapped entity ID raises UnmappedScenarioIdError, naming both the
         scenario and the entity so the failure is immediately actionable.
Dependencies: pydantic v2, typing
Used by: evals.sequence_runner
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMOTED_SCENARIO_IDS: Final[frozenset[str]] = frozenset({
    "scenario_gossip_chain",
    "scenario_grief_persistence",
    "scenario_reputation_drift",
    "scenario_memory_consolidation",
    "scenario_time_passage",
    "scenario_mood_contagion",
})

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UnmappedScenarioIdError(ValueError):
    """Raised when a scenario entity ID has no eval-world mapping.

    Attributes:
        scenario_id: The scenario that referenced the unmapped entity.
        entity_id: The entity ID for which no mapping exists.
    """

    def __init__(self, scenario_id: str, entity_id: str) -> None:
        self.scenario_id = scenario_id
        self.entity_id = entity_id
        super().__init__(
            f"Scenario {scenario_id!r} references entity {entity_id!r}"
            f" which has no eval-world mapping."
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ScenarioEntityMap(BaseModel):
    """Entity ID mapping for one promoted scenario.

    Attributes:
        scenario_id: Canonical scenario identifier (e.g. "scenario_gossip_chain").
        entities: Mapping from scenario-vocabulary entity ID to eval-world entity ID.
                  Scenarios that self-seed have an empty mapping.
    """

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    entities: dict[str, str]


class WorldMap(BaseModel):
    """Total mapping from promoted scenario entity IDs to eval-world IDs.

    Attributes:
        scenario_maps: One ScenarioEntityMap per promoted scenario.
    """

    model_config = ConfigDict(frozen=True)

    scenario_maps: tuple[ScenarioEntityMap, ...]

    def resolve(self, scenario_id: str, entity_id: str) -> str:
        """Translate a scenario entity ID to its eval-world equivalent.

        Args:
            scenario_id: Promoted scenario identifier.
            entity_id: Entity ID in the scenario's vocabulary.
        Returns:
            The corresponding eval-world entity ID.
        Raises:
            UnmappedScenarioIdError: If the scenario is not in the map, or the
                entity ID has no mapping for that scenario.
        """
        for sm in self.scenario_maps:
            if sm.scenario_id == scenario_id:
                if entity_id in sm.entities:
                    return sm.entities[entity_id]
                raise UnmappedScenarioIdError(scenario_id, entity_id)
        raise UnmappedScenarioIdError(scenario_id, entity_id)


# ---------------------------------------------------------------------------
# Canonical mapping
# ---------------------------------------------------------------------------
#
# Vocabulary reconciliation (EVAL-P12.2):
#   scenario_gossip_chain uses generic IDs seeded per-run (npc_1, npc_6, loc_market).
#   The eval world (demo seed) uses stable canonical IDs.
#   grief_persistence similarly uses elder_1 / loc_market.
#   The remaining four promoted scenarios are self-seeding or entity-free.

WORLD_MAP: Final[WorldMap] = WorldMap(
    scenario_maps=(
        ScenarioEntityMap(
            scenario_id="scenario_gossip_chain",
            entities={
                "npc_1": "aldric_merchant",
                "npc_6": "old_henryk",
                "loc_market": "loc_market_square",
                "player_1": "player_demo",
            },
        ),
        ScenarioEntityMap(
            scenario_id="scenario_grief_persistence",
            entities={
                "elder_1": "old_henryk",
                "player_1": "player_demo",
                "loc_market": "loc_market_square",
            },
        ),
        ScenarioEntityMap(
            scenario_id="scenario_reputation_drift",
            entities={},
        ),
        ScenarioEntityMap(
            scenario_id="scenario_memory_consolidation",
            entities={},
        ),
        ScenarioEntityMap(
            scenario_id="scenario_time_passage",
            entities={},
        ),
        ScenarioEntityMap(
            scenario_id="scenario_mood_contagion",
            entities={},
        ),
    )
)
