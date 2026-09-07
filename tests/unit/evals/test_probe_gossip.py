"""
Module: test_probe_gossip
Layer: test (unit)
Purpose: Tests for evals/probe_gossip.py — GossipProbe's seed/drive/measure cycle, the
         propagation/hop/distortion-delta metrics, and the source-attribution invariant.
Dependencies: pytest, unittest.mock, probe_gossip (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from unittest.mock import MagicMock

from probe_gossip import GOSSIP_PROBE_FACTORIES, GossipProbe


def _ok(payload: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


def _client_with(knowers: list[dict], chain: list[dict]) -> MagicMock:
    client = MagicMock()
    client.post.return_value = _ok({"data": {}})

    def _get(url: str, **kwargs: object) -> MagicMock:
        if url.endswith("/edges/KNOWS_ABOUT"):
            return _ok({"data": knowers})
        if "/gossip/trace/" in url:
            return _ok({"data": {"chain": chain}})
        return _ok({"data": {}})

    client.get.side_effect = _get
    return client


def test_engine_name_is_gossip() -> None:
    assert GossipProbe().engine_name == "gossip"


def test_measure_before_setup_returns_empty() -> None:
    probe = GossipProbe()
    assert probe.measure(MagicMock()) == {}


def test_invariant_before_setup_is_true() -> None:
    probe = GossipProbe()
    assert probe.invariants["knowers_have_a_source"](MagicMock()) is True


def test_full_cycle_reports_reach_hops_and_distortion_delta() -> None:
    probe = GossipProbe()
    client = _client_with(
        knowers=[
            {"src_id": "npc_probe_gossip_x", "source_character_id": None},
            {"src_id": "npc_far", "source_character_id": "npc_probe_gossip_x"},
        ],
        chain=[
            {"npc_id": "npc_probe_gossip_x", "distortion_level": 0, "learned_at_tick": 500},
            {"npc_id": "npc_far", "distortion_level": 30, "learned_at_tick": 501},
        ],
    )

    probe.setup(client)
    probe.drive(client, ticks=2)
    metrics = probe.measure(client)

    assert metrics["propagation_reach"] == 2.0
    assert metrics["hops_to_knowledge"] == 2.0
    assert metrics["distortion_delta_per_hop_mean"] == 30.0


def test_invariant_fails_when_a_non_origin_knower_has_no_source() -> None:
    probe = GossipProbe()
    seed_client = MagicMock()
    seed_client.post.return_value = _ok({"data": {}})
    probe.setup(seed_client)
    assert probe._fixture is not None
    origin_id = probe._fixture.origin_npc_id

    client = _client_with(
        knowers=[
            {"src_id": origin_id, "source_character_id": None},
            {"src_id": "npc_far", "source_character_id": None},
        ],
        chain=[],
    )

    assert probe.invariants["knowers_have_a_source"](client) is False


def test_measure_omits_distortion_delta_when_chain_has_under_two_levels() -> None:
    probe = GossipProbe()
    client = _client_with(knowers=[], chain=[{"npc_id": "solo", "distortion_level": 10}])

    probe.setup(client)
    metrics = probe.measure(client)

    assert "distortion_delta_per_hop_mean" not in metrics


def test_gossip_probe_factory_is_registered() -> None:
    assert "gossip" in GOSSIP_PROBE_FACTORIES
    probe = GOSSIP_PROBE_FACTORIES["gossip"](MagicMock())
    assert probe.engine_name == "gossip"
