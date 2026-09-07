"""
Module: test_probe_legacy_adapters
Layer: test (unit)
Purpose: Tests for evals/probe_legacy_adapters.py — LegacyScenarioProbe's structural
         EngineProbe conformance and its port of the 6 promoted scenario adapters'
         bare `() -> bool` result into a metric + invariant.
Dependencies: pytest, unittest.mock, probe_legacy_adapters (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from unittest.mock import MagicMock

from probe_legacy_adapters import LEGACY_PROBE_FACTORIES, LegacyScenarioProbe
from scenario_adapters import SCENARIO_ADAPTER_FACTORIES


def test_legacy_probe_wraps_a_passing_scenario() -> None:
    probe = LegacyScenarioProbe("scenario_x", lambda: True)
    client = MagicMock()

    probe.setup(client)
    probe.drive(client, ticks=1)
    metrics = probe.measure(client)

    assert metrics == {"scenario_holds": 1.0}
    assert probe.invariants["scenario_holds"](client) is True


def test_legacy_probe_wraps_a_failing_scenario() -> None:
    probe = LegacyScenarioProbe("scenario_x", lambda: False)
    client = MagicMock()

    probe.drive(client, ticks=1)

    assert probe.measure(client) == {"scenario_holds": 0.0}
    assert probe.invariants["scenario_holds"](client) is False


def test_invariant_reads_the_last_drive_before_any_drive_call() -> None:
    """Before drive() runs, the invariant reads the initial False, not an error."""
    probe = LegacyScenarioProbe("scenario_x", lambda: True)
    client = MagicMock()

    assert probe.invariants["scenario_holds"](client) is False


def test_engine_name_is_the_scenario_id() -> None:
    probe = LegacyScenarioProbe("scenario_gossip_chain", lambda: True)
    assert probe.engine_name == "scenario_gossip_chain"


def test_legacy_probe_factories_cover_every_promoted_scenario() -> None:
    assert set(LEGACY_PROBE_FACTORIES) == set(SCENARIO_ADAPTER_FACTORIES)


def test_a_legacy_probe_factory_builds_a_working_probe() -> None:
    client = MagicMock()
    client.post.return_value = MagicMock(status_code=200)
    client.get.return_value = MagicMock(status_code=200, json=lambda: {"data": {}})

    factory = LEGACY_PROBE_FACTORIES["scenario_gossip_chain"]
    probe = factory(client)

    assert probe.engine_name == "scenario_gossip_chain"
    assert "scenario_holds" in probe.invariants
