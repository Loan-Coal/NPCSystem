"""
simulate_world_flow.py - Deterministic world-flow simulator for v1.4 smoke verification.

Does NOT: write to Neo4j or call LLM backends.

Dependencies injected: None.
"""

from __future__ import annotations

import json
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field


ACTION_QUEST_COMPLETE = "quest_complete"
ACTION_TRADE_BUY = "trade_buy"
ACTION_TRADE_SELL = "trade_sell"
ACTION_GREET = "greet"
ACTION_INVESTIGATE = "investigate"
ACTION_RUMOR = "rumor"
ACTION_FAREWELL = "farewell"
ACTION_QUEST_ACCEPT = "quest_accept"

DEFAULT_TURN_SEQUENCE: tuple[str, ...] = (
    ACTION_GREET,
    ACTION_INVESTIGATE,
    "quest_offer",
    ACTION_QUEST_ACCEPT,
    ACTION_TRADE_BUY,
    ACTION_RUMOR,
    ACTION_TRADE_SELL,
    ACTION_QUEST_COMPLETE,
    ACTION_FAREWELL,
    "idle",
)

RELATION_MUTATION_ACTIONS = frozenset(
    {
        ACTION_GREET,
        ACTION_INVESTIGATE,
        ACTION_RUMOR,
        ACTION_FAREWELL,
        ACTION_QUEST_ACCEPT,
        ACTION_QUEST_COMPLETE,
    }
)
CURRENCY_TRANSFER_ACTIONS = frozenset({ACTION_TRADE_BUY, ACTION_TRADE_SELL})

BASE_GRAPH_NODE_COUNT = 18
QUEST_COMPLETION_NODE_BONUS = 1
MIN_EXPECTED_QUEST_COMPLETIONS = 1
MIN_EXPECTED_CURRENCY_TRANSFERS = 1

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


class SimulationSummary(BaseModel):
    """Stable summary payload for v1.4 world-flow simulation."""

    nodes_created: int = Field(ge=0)
    dialogue_turns: int = Field(ge=0)
    quests_completed: int = Field(ge=0)
    currency_transfers: int = Field(ge=0)
    relation_deltas: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True, strict=True)


def _count_actions(turn_sequence: Sequence[str], target_actions: frozenset[str]) -> int:
    """Count actions from a turn sequence that match a target action set."""

    return sum(1 for action in turn_sequence if action in target_actions)


def _collect_simulation_errors(quests_completed: int, currency_transfers: int) -> list[str]:
    """Build deterministic validation errors for the simulation summary."""

    errors: list[str] = []
    if quests_completed < MIN_EXPECTED_QUEST_COMPLETIONS:
        errors = [*errors, "quest_completion_missing"]
    if currency_transfers < MIN_EXPECTED_CURRENCY_TRANSFERS:
        errors = [*errors, "currency_transfer_missing"]
    return errors


def run_simulation(turn_sequence: Sequence[str] = DEFAULT_TURN_SEQUENCE) -> SimulationSummary:
    """Run deterministic world-flow simulation and return a stable summary model."""

    dialogue_turns = len(turn_sequence)
    quests_completed = turn_sequence.count(ACTION_QUEST_COMPLETE)
    currency_transfers = _count_actions(turn_sequence=turn_sequence, target_actions=CURRENCY_TRANSFER_ACTIONS)
    relation_deltas = _count_actions(turn_sequence=turn_sequence, target_actions=RELATION_MUTATION_ACTIONS)
    nodes_created = BASE_GRAPH_NODE_COUNT + (quests_completed * QUEST_COMPLETION_NODE_BONUS)
    errors = _collect_simulation_errors(
        quests_completed=quests_completed,
        currency_transfers=currency_transfers,
    )
    return SimulationSummary(
        nodes_created=nodes_created,
        dialogue_turns=dialogue_turns,
        quests_completed=quests_completed,
        currency_transfers=currency_transfers,
        relation_deltas=relation_deltas,
        errors=errors,
    )


def format_summary_json(summary: SimulationSummary) -> str:
    """Serialize simulation summary to stable, sorted JSON."""

    return json.dumps(summary.model_dump(), sort_keys=True)


def main() -> int:
    """Run simulation CLI entry point and return shell exit code."""

    summary = run_simulation()
    print(format_summary_json(summary=summary))
    return EXIT_SUCCESS if not summary.errors else EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
