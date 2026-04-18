"""
test_simulate_world_flow_v14.py - Tests deterministic v1.4 world-flow simulation summary.

Does NOT: access Neo4j or external LLM services.

Dependencies injected: None.
"""

import scripts.simulate_world_flow as simulator


EXPECTED_SUMMARY = {
    "currency_transfers": 2,
    "dialogue_turns": 10,
    "errors": [],
    "nodes_created": 19,
    "quests_completed": 1,
    "relation_deltas": 6,
}
EXPECTED_JSON = '{"currency_transfers": 2, "dialogue_turns": 10, "errors": [], "nodes_created": 19, "quests_completed": 1, "relation_deltas": 6}'


def test_run_simulation_returns_expected_default_summary() -> None:
    """Default simulation should produce a stable, deterministic summary payload."""

    summary = simulator.run_simulation()

    assert summary.model_dump() == EXPECTED_SUMMARY


def test_format_summary_json_is_stable_and_sorted() -> None:
    """JSON formatter should produce a stable, sorted representation."""

    summary = simulator.run_simulation()
    first_json = simulator.format_summary_json(summary=summary)
    second_json = simulator.format_summary_json(summary=summary)

    assert first_json == EXPECTED_JSON
    assert second_json == EXPECTED_JSON


def test_run_simulation_reports_required_error_codes_for_missing_actions() -> None:
    """Simulation should report deterministic errors when required actions are absent."""

    summary = simulator.run_simulation(turn_sequence=("idle",))

    assert summary.errors == ["quest_completion_missing", "currency_transfer_missing"]


def test_main_returns_failure_when_simulation_contains_errors(monkeypatch) -> None:
    """CLI entry point should return failure exit code for error summaries."""

    error_summary = simulator.run_simulation(turn_sequence=("idle",))
    monkeypatch.setattr(simulator, "run_simulation", lambda: error_summary)

    assert simulator.main() == simulator.EXIT_FAILURE
