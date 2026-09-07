"""
Module: test_probe_protocol
Layer: test (unit)
Purpose: Tests for evals/probe_protocol.py — the EngineProbe structural contract.
         A Protocol has no runtime behaviour of its own, so these tests confirm a
         minimal concrete implementation satisfies it (ISP/LSP: the mock matches
         the real contract's shape) and that InvariantFn is callable as declared.
Dependencies: pytest, probe_protocol (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from probe_protocol import EngineProbe


class _StubProbe:
    """Minimal concrete EngineProbe — exercises every protocol member."""

    def __init__(self) -> None:
        self.engine_name = "gossip"
        self.invariants: dict[str, object] = {"reach_positive": lambda client: True}
        self.setup_calls = 0
        self.drive_calls: list[int] = []
        self.measure_calls = 0

    def setup(self, client: httpx.Client) -> None:
        self.setup_calls += 1

    def drive(self, client: httpx.Client, ticks: int) -> None:
        self.drive_calls.append(ticks)

    def measure(self, client: httpx.Client) -> dict[str, float]:
        self.measure_calls += 1
        return {"reach": 1.0}


def test_stub_probe_structurally_satisfies_engine_probe() -> None:
    """A minimal concrete class with matching members is a valid EngineProbe."""
    probe: EngineProbe = _StubProbe()
    assert probe.engine_name == "gossip"
    assert "reach_positive" in probe.invariants


def test_setup_drive_measure_are_callable_in_declared_order() -> None:
    """setup(client) -> drive(client, ticks) -> measure(client) all run without error."""
    probe = _StubProbe()
    client: httpx.Client = MagicMock()

    probe.setup(client)
    probe.drive(client, ticks=2)
    metrics = probe.measure(client)

    assert probe.setup_calls == 1
    assert probe.drive_calls == [2]
    assert metrics == {"reach": 1.0}


def test_invariant_fn_is_a_plain_callable_over_the_client() -> None:
    """An invariant takes the client and returns a bool."""
    probe = _StubProbe()
    client: httpx.Client = MagicMock()
    result = probe.invariants["reach_positive"](client)
    assert result is True
