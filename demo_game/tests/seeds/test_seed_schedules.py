"""
Module: test_seed_schedules
Layer: demo_game (tests)
Purpose: TDD unit tests for schedule seeding — verifies Schedule nodes and
         FOLLOWS_SCHEDULE edges are created for the three demo MetaHumans
         (mira_innkeeper, captain_sorn, lira_fence) plus the gossip-path
         terminal node (old_henryk).
Dependencies: demo_game.seeds.seed_domain, demo_game.seeds.seed_world_data,
              demo_game.seeds.seed_npc_data, unittest.mock (no network required)
Used by: pytest demo_game/tests/seeds/
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from demo_game.seeds.seed_domain import _seed_schedules
from demo_game.seeds.seed_npc_data import H2_DISTRICTS, H2_LOCATIONS
from demo_game.seeds.seed_world_data import _LOCATIONS, _SCHEDULES


# ---------------------------------------------------------------------------
# All valid location IDs in the seed (used to validate schedule entries)
# ---------------------------------------------------------------------------

_ALL_LOCATION_IDS: frozenset[str] = frozenset(
    {t[0] for t in _LOCATIONS}
    | {t[0] for t in H2_LOCATIONS}
    | {t[0] for t in H2_DISTRICTS}
    | {"loc_city"}
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client_fresh() -> MagicMock:
    """Mock EngineClient simulating an empty database (nothing exists yet)."""
    client = MagicMock()
    client.get_node.return_value = None
    client.get_edge.return_value = None
    client.upsert_node.return_value = {"data": {}}
    client.upsert_edge.return_value = {"data": {}}
    return client


def _mock_client_full() -> MagicMock:
    """Mock EngineClient simulating a fully-seeded database (all items exist)."""
    client = MagicMock()
    client.get_node.return_value = {"id": "existing"}
    client.get_edge.return_value = {"src_id": "a", "dst_id": "b"}
    client.upsert_node.return_value = {"data": {}}
    client.upsert_edge.return_value = {"data": {}}
    return client


# ---------------------------------------------------------------------------
# Data integrity tests (no client needed)
# ---------------------------------------------------------------------------


def test_schedules_data_non_empty() -> None:
    """_SCHEDULES must be populated — zero entries means routine_engine has nothing."""
    assert len(_SCHEDULES) > 0, "zero schedules found — _SCHEDULES must be populated"


def test_gossip_path_npcs_have_schedules() -> None:
    """Every NPC on the gossip chain (captain_sorn → mira_innkeeper → old_henryk) must have a schedule."""
    gossip_path: frozenset[str] = frozenset({"captain_sorn", "mira_innkeeper", "old_henryk"})
    scheduled_chars = {entry[1] for entry in _SCHEDULES}
    missing = gossip_path - scheduled_chars
    assert not missing, f"Gossip-path NPCs missing from _SCHEDULES: {missing}"


def test_metahuman_npcs_have_schedules() -> None:
    """All three demo MetaHumans (Mira, Sorn, Lira) must have a schedule."""
    metahumans: frozenset[str] = frozenset({"mira_innkeeper", "captain_sorn", "lira_fence"})
    scheduled_chars = {entry[1] for entry in _SCHEDULES}
    missing = metahumans - scheduled_chars
    assert not missing, f"MetaHuman NPCs missing from _SCHEDULES: {missing}"


def test_schedule_entries_reference_valid_location_ids() -> None:
    """Every time-of-day slot in every schedule must reference a seeded location_id."""
    for schedule_id, character_id, _name, _desc, entries in _SCHEDULES:
        for entry in entries:
            loc_id = entry["location_id"]
            assert loc_id in _ALL_LOCATION_IDS, (
                f"Schedule {schedule_id!r} for {character_id!r}: "
                f"slot references unknown location_id {loc_id!r}"
            )


def test_schedule_entries_have_valid_time_of_day() -> None:
    """Every slot must use one of the five valid time_of_day values."""
    valid_times = frozenset({"morning", "midday", "afternoon", "evening", "night"})
    for schedule_id, character_id, _name, _desc, entries in _SCHEDULES:
        for entry in entries:
            tod = entry.get("time_of_day", "")
            assert tod in valid_times, (
                f"Schedule {schedule_id!r}: invalid time_of_day {tod!r}"
            )


# ---------------------------------------------------------------------------
# Seeding behaviour tests (mock client)
# ---------------------------------------------------------------------------


def test_schedule_node_created_for_each_schedule_on_fresh_db() -> None:
    """Every entry in _SCHEDULES must produce a 'Schedule' upsert_node call."""
    client = _mock_client_fresh()
    _seed_schedules(client)

    schedule_upserts = [
        c for c in client.upsert_node.call_args_list
        if c.args[0] == "Schedule"
    ]
    created_ids = {c.args[1]["id"] for c in schedule_upserts}
    expected_ids = {entry[0] for entry in _SCHEDULES}

    assert created_ids == expected_ids, (
        f"Missing Schedule upserts for: {expected_ids - created_ids}"
    )


def test_follows_schedule_edge_created_for_each_character_on_fresh_db() -> None:
    """Every entry in _SCHEDULES must produce a FOLLOWS_SCHEDULE upsert_edge call."""
    client = _mock_client_fresh()
    _seed_schedules(client)

    follows_calls = [
        c for c in client.upsert_edge.call_args_list
        if c.args[0] == "FOLLOWS_SCHEDULE"
    ]
    actual_chars = {c.args[1] for c in follows_calls}
    expected_chars = {entry[1] for entry in _SCHEDULES}

    assert actual_chars == expected_chars, (
        f"Missing FOLLOWS_SCHEDULE edges for: {expected_chars - actual_chars}"
    )


def test_schedule_entries_stored_as_json_string() -> None:
    """The 'entries' property on each seeded Schedule node must be valid JSON."""
    client = _mock_client_fresh()
    _seed_schedules(client)

    schedule_upserts = [
        c for c in client.upsert_node.call_args_list
        if c.args[0] == "Schedule"
    ]
    for upsert_call in schedule_upserts:
        payload = upsert_call.args[1]
        entries_raw = payload.get("entries", "")
        parsed = json.loads(entries_raw)
        assert isinstance(parsed, list), (
            f"Schedule {payload['id']!r}: entries is not a JSON array"
        )
        assert len(parsed) > 0, (
            f"Schedule {payload['id']!r}: entries array is empty"
        )


def test_seed_schedules_is_idempotent() -> None:
    """_seed_schedules on a fully-seeded DB creates zero items."""
    client = _mock_client_full()
    count = _seed_schedules(client)
    assert count == 0, f"Expected 0 on idempotent call, got {count}"


def test_seed_schedules_returns_correct_count_on_fresh_db() -> None:
    """_seed_schedules returns one count per Schedule node plus one per edge."""
    client = _mock_client_fresh()
    count = _seed_schedules(client)
    expected = len(_SCHEDULES) * 2  # one Schedule node + one edge each
    assert count == expected, f"Expected {expected} items created, got {count}"
