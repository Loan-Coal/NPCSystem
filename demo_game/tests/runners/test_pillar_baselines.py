"""
Module: test_pillar_baselines
Layer: demo_game (tests)
Purpose: T25.9 — each pillar check compares a baseline read with an after read, so a
         transcript showing the old bug is red and a fixed one is green.  The 2026-11-16
         audit found GOSSIP and FEEL green before their fixes, and REMEMBER green on
         interaction_count alone; these cases replay what the live stack showed.
Dependencies: demo_game.runners.pillars
Used by: make test-demo
"""

from __future__ import annotations

from typing import Any

from demo_game.runners.pillars import (
    BASELINE_DONE,
    DEMO_DONE,
    SEEDED_NPC_LOCATIONS,
    check_feel,
    check_gossip,
    check_remember,
    check_world,
)

TranscriptEntry = dict[str, Any]


def _entry(method: str, path: str, body: object, status: int = 200) -> TranscriptEntry:
    return {"method": method, "path": path, "status": status, "body": body}


_BASELINE_MARK = _entry("MARK", BASELINE_DONE, None, status=0)
_DEMO_MARK = _entry("MARK", DEMO_DONE, None, status=0)
_FIRE = _entry("PATCH", "/v1/graph/nodes/world_state/world", {"data": {"id": "world"}})


def _emotion(valence: int, arousal: int) -> TranscriptEntry:
    return _entry("GET", "/v1/npc/aldric_merchant/emotion", {"valence": valence, "arousal": arousal})


def _relationship(trust: int, fear: int, affection: int) -> TranscriptEntry:
    body = {"data": {"trust": trust, "fear": fear, "affection": affection, "interaction_count": 4}}
    return _entry("GET", "/v1/npc/mira_innkeeper/relationship/player_demo", body)


_NO_RELATIONSHIP = _entry("GET", "/v1/npc/mira_innkeeper/relationship/player_demo", None, status=404)
_MEMORY = _entry("POST", "/v1/admin/memories/consolidate/mira_innkeeper", {"data": {"memory_id": "m1"}})


def _knows(*edges: dict) -> TranscriptEntry:
    return _entry("GET", "/v1/graph/edges/KNOWS_ABOUT", {"data": list(edges)})


def _edge(src: str, event: str, level: int, source: str | None) -> dict:
    return {"src_id": src, "dst_id": event, "distortion_level": level, "source_character_id": source}


_SEEDED_CHAIN = (
    _edge("captain_sorn", "northern_war_begins", 0, None),
    _edge("mira_innkeeper", "northern_war_begins", 20, "captain_sorn"),
    _edge("old_henryk", "northern_war_begins", 70, "mira_innkeeper"),
    _edge("lira_fence", "rumor_plant", 56, "player"),
)


def _located(locations: dict[str, tuple[str, int]]) -> list[TranscriptEntry]:
    return [
        _entry("GET", "/v1/graph/edges/LOCATED_AT", {"data": [{"src_id": npc, "dst_id": loc, "arrived_at_tick": tick}]})
        for npc, (loc, tick) in locations.items()
    ]


_SEEDED_START = {npc: (loc, 0) for npc, loc in SEEDED_NPC_LOCATIONS.items()}


# ---------------------------------------------------------------------------
# FEEL: the witness's emotion moves across the event, not merely "non-neutral"
# ---------------------------------------------------------------------------

def test_feel_red_when_the_event_leaves_a_non_neutral_emotion_unchanged() -> None:
    """Pre-T25.4: no shock, but a non-neutral seeded mood passed the old check."""
    entries = [_emotion(-5, 10), _BASELINE_MARK, _FIRE, _emotion(-5, 10), _DEMO_MARK]

    ok, evidence = check_feel(entries)

    assert not ok, evidence


def test_feel_green_when_the_event_moves_the_emotion() -> None:
    entries = [_emotion(-5, 10), _BASELINE_MARK, _FIRE, _emotion(-35, 60), _DEMO_MARK]

    ok, evidence = check_feel(entries)

    assert ok, evidence
    assert "-5/10 -> -35/60" in evidence


def test_feel_red_without_a_read_after_the_event() -> None:
    entries = [_emotion(-5, 10), _BASELINE_MARK, _FIRE, _DEMO_MARK]

    ok, _ = check_feel(entries)

    assert not ok


# ---------------------------------------------------------------------------
# REMEMBER: dialogue moves trust, fear or affection — interaction_count is not enough
# ---------------------------------------------------------------------------

def test_remember_red_when_dialogue_counts_turns_but_moves_nothing() -> None:
    """The 2026-11-16 live run: interaction_count 4, deltas 0/0/0. The old check said green."""
    entries = [_NO_RELATIONSHIP, _BASELINE_MARK, _MEMORY, _DEMO_MARK, _relationship(0, 0, 0)]

    ok, evidence = check_remember(entries)

    assert not ok, evidence


def test_remember_green_when_a_delta_moves_and_a_memory_is_created() -> None:
    entries = [_NO_RELATIONSHIP, _BASELINE_MARK, _MEMORY, _DEMO_MARK, _relationship(0, 0, 3)]

    ok, evidence = check_remember(entries)

    assert ok, evidence


def test_remember_red_without_a_baseline_read() -> None:
    entries = [_BASELINE_MARK, _MEMORY, _DEMO_MARK, _relationship(5, 0, 0)]

    ok, _ = check_remember(entries)

    assert not ok


# ---------------------------------------------------------------------------
# GOSSIP: an engine-propagated hop exists, and its distortion compounds
# ---------------------------------------------------------------------------

def test_gossip_red_when_only_the_seeded_chain_exists() -> None:
    """The seed already holds Sorn→Mira→Henryk (DEC-006); the old check only read it."""
    entries = [_knows(*_SEEDED_CHAIN), _BASELINE_MARK, _DEMO_MARK, _knows(*_SEEDED_CHAIN)]

    ok, evidence = check_gossip(entries)

    assert not ok, evidence


def test_gossip_red_when_a_new_hop_stores_no_distortion() -> None:
    """Pre-T25.3: hops were written with distortion_level 0."""
    hop = _edge("nel_pickpocket", "rumor_plant", 0, "lira_fence")
    entries = [_knows(*_SEEDED_CHAIN), _BASELINE_MARK, _DEMO_MARK, _knows(*_SEEDED_CHAIN, hop)]

    ok, evidence = check_gossip(entries)

    assert not ok, evidence


def test_gossip_red_when_a_hop_loses_distortion() -> None:
    hop = _edge("nel_pickpocket", "rumor_plant", 30, "lira_fence")
    entries = [_knows(*_SEEDED_CHAIN), _BASELINE_MARK, _DEMO_MARK, _knows(*_SEEDED_CHAIN, hop)]

    ok, _ = check_gossip(entries)

    assert not ok


def test_gossip_red_when_the_only_hop_builds_on_an_undistorted_source() -> None:
    """Live proof at 7d2103a1 (pre-T25.3): "75 >= source 0" passed although nothing compounded.

    A hop over a source at level 0 shows fresh distortion, not distortion carried forward.
    """
    zero_source = _edge("dorn_dockmaster", "northern_war_begins", 75, "captain_sorn")
    entries = [_knows(*_SEEDED_CHAIN), _BASELINE_MARK, _DEMO_MARK, _knows(*_SEEDED_CHAIN, zero_source)]

    ok, evidence = check_gossip(entries)

    assert not ok, evidence


def test_gossip_green_when_a_new_hop_compounds() -> None:
    """The live run: Lira (56, from the player) told Nel at tick 10 at 56."""
    hop = _edge("nel_pickpocket", "rumor_plant", 56, "lira_fence")
    entries = [_knows(*_SEEDED_CHAIN), _BASELINE_MARK, _DEMO_MARK, _knows(*_SEEDED_CHAIN, hop)]

    ok, evidence = check_gossip(entries)

    assert ok, evidence


def test_gossip_ignores_edges_the_player_planted() -> None:
    """A player-sourced edge that appears during the run is not engine gossip."""
    planted = _edge("sera_barmaid", "rumor_plant", 60, "player")
    entries = [_knows(*_SEEDED_CHAIN), _BASELINE_MARK, _DEMO_MARK, _knows(*_SEEDED_CHAIN, planted)]

    ok, _ = check_gossip(entries)

    assert not ok


# ---------------------------------------------------------------------------
# WORLD: everyone starts where seeded; a move carries a real arrival tick
# ---------------------------------------------------------------------------

def _world(start: dict[str, tuple[str, int]], end: dict[str, tuple[str, int]]) -> list[TranscriptEntry]:
    return [*_located(start), _BASELINE_MARK, _DEMO_MARK, *_located(end)]


def test_world_green_when_a_need_moves_an_npc_with_an_arrival_tick() -> None:
    """Owner, 2026-11-16: NPCs start where seeded and may move as the demo runs."""
    end = {**_SEEDED_START, "nel_pickpocket": ("loc_market_square", 10)}

    ok, evidence = check_world(_world(_SEEDED_START, end))

    assert ok, evidence
    assert "nel_pickpocket" in evidence


def test_world_red_when_a_move_has_arrival_tick_zero() -> None:
    """ISSUE-373's signature: moved NPCs stamped arrived_at_tick 0."""
    end = {**_SEEDED_START, "nel_pickpocket": ("loc_market_square", 0)}

    ok, _ = check_world(_world(_SEEDED_START, end))

    assert not ok


def test_world_red_when_everyone_snaps_to_one_location() -> None:
    end = {npc: ("loc_temple", 5) for npc in SEEDED_NPC_LOCATIONS}

    ok, evidence = check_world(_world(_SEEDED_START, end))

    assert not ok, evidence


def test_world_red_when_the_start_is_not_the_seed() -> None:
    start = {**_SEEDED_START, "mira_innkeeper": ("loc_temple", 0)}

    ok, evidence = check_world(_world(start, _SEEDED_START))

    assert not ok, evidence
    assert "mira_innkeeper" in evidence
