"""
test_village_reputation_seed.py - the seeded reputation acts must match the query that reads them.

`system_v1.yaml` Rule 13 spends ~19 lines teaching the model how to read
`context.propagated_reputation`, and that list was `[]` in 975 of 975 recorded rows. P6 wired
the producer; this is the data that makes it non-empty.

The failure this guards is quiet and expensive: `CYPHER_PROPAGATED_REPUTATION_FOR_NPC` matches
on `event_type = 'reputation_change'` AND `src_character_id = <the turn's player>`, and reads
`faction_id`, `reputation_delta` and `knowledge_state` by name. Miss any one of those and the
seed runs clean, the graph looks populated, and the slot is still empty -- which is
indistinguishable from the bug it was meant to fix.

Does NOT: execute I/O, connect to Neo4j, or run the seeder. It reads the declared data and
the Cypher text.
"""

from __future__ import annotations

import pathlib

import pytest

from npc_engine.graph.reputation.reputation_queries import (
    CYPHER_PROPAGATED_REPUTATION_FOR_NPC,
    _PROPAGATED_REP_LIMIT,
)
from npc_engine.graph.reputation.reputation_event_seeder import REPUTATION_EVENT_TYPE
from seeds.worlds.seed_village_world import (
    _REPUTATION_EVENT_TYPE,
    _REPUTATION_EVENTS,
    _REPUTATION_KNOWS_ABOUT,
    _REPUTATION_PLAYER_ID,
    build_event_payload,
)

_BASELINE = pathlib.Path(__file__).resolve().parents[3] / "evals" / "fixtures" / "eval_world_baseline.json"


def _payloads() -> list[dict]:
    return [
        build_event_payload(
            id=evt_id, summary=summary, event_type=_REPUTATION_EVENT_TYPE,
            location_id=location_id, severity=severity, is_public=True,
            src_character_id=_REPUTATION_PLAYER_ID, faction_id=faction_id,
            reputation_delta=delta,
        )
        for evt_id, summary, location_id, severity, faction_id, delta in _REPUTATION_EVENTS
    ]


def test_the_seeder_event_type_matches_the_engine_constant() -> None:
    """The seeders may not import npc_engine, so the mirror is pinned here instead."""
    assert _REPUTATION_EVENT_TYPE == REPUTATION_EVENT_TYPE


@pytest.mark.parametrize("field", ["event_type", "src_character_id", "faction_id", "reputation_delta"])
def test_every_seeded_event_carries_the_field_the_query_matches_or_returns(field: str) -> None:
    """Miss one and the seed runs clean while the slot stays empty."""
    assert field in CYPHER_PROPAGATED_REPUTATION_FOR_NPC
    for payload in _payloads():
        assert field in payload, f"{payload['id']} has no {field}"


def test_an_ordinary_event_gains_no_reputation_fields() -> None:
    """The three new arguments must be absent, not null, so existing events do not move."""
    payload = build_event_payload(
        id="vw_crop_blight", summary="a blight", event_type="disaster",
        location_id="vw_farmland", severity=65, is_public=True,
    )
    assert "src_character_id" not in payload
    assert "faction_id" not in payload
    assert "reputation_delta" not in payload


def test_both_signs_of_reputation_are_represented() -> None:
    """Rule 13 has a warmth branch and a suspicion branch; an eval must be able to hit both."""
    deltas = [p["reputation_delta"] for p in _payloads()]
    assert any(d > 0 for d in deltas), "no positive act: Rule 13's warmth branch is unreachable"
    assert any(d < 0 for d in deltas), "no negative act: Rule 13's suspicion branch is unreachable"


def test_both_knowledge_states_are_represented() -> None:
    """Rule 13 requires hedging for a rumour and forbids it for confirmed word."""
    states = {state for _, _, state, _ in _REPUTATION_KNOWS_ABOUT}
    assert states == {"rumor", "knows"}


def test_every_knows_about_edge_points_at_a_seeded_event() -> None:
    """A typo here is a dangling edge the seeder reports as created."""
    seeded = {payload["id"] for payload in _payloads()}
    for _npc, event_id, _state, _summary in _REPUTATION_KNOWS_ABOUT:
        assert event_id in seeded, f"KNOWS_ABOUT points at unseeded event {event_id!r}"


def test_the_acts_fit_under_the_query_limit() -> None:
    """More acts than the LIMIT would make which ones surface an ordering accident."""
    assert len(_REPUTATION_EVENTS) <= _PROPAGATED_REP_LIMIT


def test_the_attributed_player_exists_in_the_checked_in_baseline() -> None:
    """An act attributed to a player with no Character node is one no NPC can ever recall.

    This is why the acts are attributed to `player_demo` and not `player_eval`: the baseline
    contains exactly one player Character, and the query matches the TURN's player id.
    """
    import json

    with open(_BASELINE, encoding="utf-8") as handle:
        world = json.load(handle)
    players = {
        node["props"].get("id")
        for node in world["nodes"]
        if "Character" in (node.get("labels") or []) and node["props"].get("is_player")
    }
    assert _REPUTATION_PLAYER_ID in players, (
        f"{_REPUTATION_PLAYER_ID!r} is not a player in the eval-world baseline; "
        f"players present: {sorted(p for p in players if p)}"
    )
