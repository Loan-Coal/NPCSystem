"""
Module: probe_legacy_adapters
Layer: evals (eval harness — not part of src/)
Purpose: Port the 6 EVAL-P12.4 promoted scenario adapters (scenario_adapters.py,
         scenario_adapters_extra.py) to the EngineProbe protocol (measurement-remediation
         Phase 4, DEC-271). Each scenario's original bare `() -> bool` predicate becomes
         both an invariant ("the scenario's assertion held") and a metric
         (scenario_holds: 1.0/0.0) — the minimal, literal port: these six scenarios were
         authored as single build->act->assert units with no natural setup/drive/measure
         seam, so this wraps rather than restructures them.
Dependencies: httpx, probe_protocol (evals/), scenario_adapters, scenario_adapters_extra
Used by: probe_runner.PROBE_FACTORIES
Does NOT: change scenario_adapters.py/scenario_adapters_extra.py, or alter what any of the
          6 scenarios build, tick, or assert — LegacyScenarioProbe only adapts the calling
          convention.
"""

from __future__ import annotations

from typing import Callable

import httpx

from probe_protocol import EngineProbe
from scenario_adapters import SCENARIO_ADAPTER_FACTORIES

ScenarioFn = Callable[[], bool]
LegacyProbeFactory = Callable[[httpx.Client], EngineProbe]

# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class LegacyScenarioProbe:
    """Wraps one ScenarioFn (`() -> bool`) as an EngineProbe.

    The legacy scenario performs its own build, tick, and assert in one call — there is
    no seam to split into separate setup/drive/measure steps without rewriting the
    scenario itself, which is out of scope here (the scenarios are unchanged). So:
    setup() is a no-op (the scenario builds its own fresh entities per call, same as it
    always has under sequence_runner), drive() runs the whole scenario and remembers the
    result, and measure() reports it as a metric. The same remembered result also backs
    the probe's one invariant, via a closure over self rather than the unused `client`
    argument InvariantFn's signature requires.
    """

    def __init__(self, engine_name: str, scenario_fn: ScenarioFn) -> None:
        """Wrap one scenario callable as an EngineProbe for the given engine name.

        Args:
            engine_name: Engine key this scenario measures (used for free engine_status
                merge in probe_runner — matches a tick-registered engine's key when one
                exists, e.g. "mood_contagion"; otherwise the probe simply gets no merge).
            scenario_fn: The zero-arg `() -> bool` closure a SCENARIO_ADAPTER_FACTORIES
                factory returns.
        """
        self.engine_name = engine_name
        self._scenario_fn = scenario_fn
        self._last_result: bool = False
        self.invariants = {"scenario_holds": self._invariant_scenario_holds}

    def _invariant_scenario_holds(self, client: httpx.Client) -> bool:
        """Return the legacy scenario's own assertion result from the last drive() call."""
        del client  # unused: the result was already captured by drive()
        return self._last_result

    def setup(self, client: httpx.Client) -> None:
        """No-op: the wrapped scenario builds its own fresh entities per call."""
        del client

    def drive(self, client: httpx.Client, ticks: int) -> None:
        """Run the wrapped scenario once, storing its bool result.

        `ticks` is unused: each legacy scenario hardcodes its own tick count internally
        (e.g. gossip_chain always runs 2 gossip ticks) — that is unchanged behaviour, not
        a gap this port fills.
        """
        del client, ticks  # the scenario closure already carries its own client
        self._last_result = self._scenario_fn()

    def measure(self, client: httpx.Client) -> dict[str, float]:
        """Report the legacy scenario's result as a 1.0/0.0 metric."""
        del client
        return {"scenario_holds": 1.0 if self._last_result else 0.0}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def _make_legacy_probe_factory(scenario_id: str) -> LegacyProbeFactory:
    """Build a ProbeFactory for one legacy scenario, keyed by its own scenario_id.

    Args:
        scenario_id: Key into SCENARIO_ADAPTER_FACTORIES (e.g. "scenario_gossip_chain").
    Returns:
        A ProbeFactory closure: given an httpx.Client, builds the scenario's `() -> bool`
        closure via the original factory, then wraps it in a LegacyScenarioProbe.
    """

    def _factory(client: httpx.Client) -> EngineProbe:
        scenario_fn = SCENARIO_ADAPTER_FACTORIES[scenario_id](client)
        return LegacyScenarioProbe(scenario_id, scenario_fn)

    return _factory


LEGACY_PROBE_FACTORIES: dict[str, LegacyProbeFactory] = {
    scenario_id: _make_legacy_probe_factory(scenario_id) for scenario_id in SCENARIO_ADAPTER_FACTORIES
}
