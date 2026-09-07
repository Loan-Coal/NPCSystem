"""
Module: test_probe_memory
Layer: test (unit)
Purpose: Tests for evals/probe_memory.py — MemoryProbe's dialogue-to-consolidation
         drive, the recall-precision/decay-curve/compression-ratio metrics, and the
         memory-is-remembered invariant.
Dependencies: pytest, unittest.mock, probe_memory (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from probe_memory import MEMORY_PROBE_FACTORIES, MemoryProbe


def _ok(payload: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


def _client(memory_id: str = "mem_1", vividness_before: float = 75.0, vividness_after: float = 55.0) -> MagicMock:
    client = MagicMock()
    state = {"vividness": vividness_before}

    def _post(url: str, **kwargs: object) -> MagicMock:
        if "/memories/consolidate/" in url:
            return _ok({"data": {"memory_id": memory_id}})
        if url.endswith("/memories/decay"):
            state["vividness"] = vividness_after
            return _ok({"data": {"decayed_count": 1}})
        return _ok({"data": {}})

    def _get(url: str, **kwargs: object) -> MagicMock:
        if "/memories/" in url:
            return _ok({"data": {"memories": [{"id": memory_id, "vividness": state["vividness"]}]}})
        return _ok({"data": {}})

    client.post.side_effect = _post
    client.get.side_effect = _get
    return client


def test_engine_name_is_memory() -> None:
    assert MemoryProbe().engine_name == "memory"


def test_measure_before_setup_returns_empty() -> None:
    assert MemoryProbe().measure(MagicMock()) == {}


@patch("probe_memory.ensure_player_node")
def test_full_cycle_reports_precision_ratio_and_decay(mock_ensure: MagicMock) -> None:
    probe = MemoryProbe()
    client = _client()

    probe.setup(client)
    probe.drive(client, ticks=6)
    metrics = probe.measure(client)

    assert metrics["recall_precision"] == 1.0
    assert metrics["consolidation_compression_ratio"] == 6.0
    assert metrics["decay_curve_delta"] == 55.0 - 75.0


@patch("probe_memory.ensure_player_node")
def test_drive_caps_turn_count_at_the_fixed_message_list_length(mock_ensure: MagicMock) -> None:
    probe = MemoryProbe()
    client = _client()

    probe.setup(client)
    probe.drive(client, ticks=999)

    assert probe._turn_count == 6


@patch("probe_memory.ensure_player_node")
def test_invariant_holds_when_memory_is_recalled(mock_ensure: MagicMock) -> None:
    probe = MemoryProbe()
    client = _client()
    probe.setup(client)
    probe.drive(client, ticks=6)

    assert probe.invariants["memory_is_remembered"](client) is True


@patch("probe_memory.ensure_player_node")
def test_invariant_fails_when_consolidation_produced_nothing(mock_ensure: MagicMock) -> None:
    probe = MemoryProbe()
    client = MagicMock()
    client.post.return_value = _ok({"data": {}})  # no memory_id in consolidate response
    client.get.return_value = _ok({"data": {"memories": []}})

    probe.setup(client)
    probe.drive(client, ticks=6)
    metrics = probe.measure(client)

    assert metrics["recall_precision"] == 0.0
    assert metrics["consolidation_compression_ratio"] == 0.0
    assert "decay_curve_delta" not in metrics


def test_memory_probe_factory_is_registered() -> None:
    assert "memory" in MEMORY_PROBE_FACTORIES
    probe = MEMORY_PROBE_FACTORIES["memory"](MagicMock())
    assert probe.engine_name == "memory"
