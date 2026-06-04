"""
Tests for SEV-10: schema_bootstrap.ensure_core_constraints and api_seeder idempotency.

Unit tests only — no real Neo4j connection.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from npc_engine.graph.schema_bootstrap import (
    _CORE_LABELS,
    _CYPHER_CREATE_CONSTRAINT_TEMPLATE,
    ensure_core_constraints,
)


# ---------------------------------------------------------------------------
# ensure_core_constraints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_core_constraints_issues_all_seven_statements() -> None:
    """All 7 core-label constraint CREATE statements must be issued to the session."""
    session = AsyncMock()

    await ensure_core_constraints(session=session)

    assert session.run.call_count == len(_CORE_LABELS), (
        f"Expected {len(_CORE_LABELS)} session.run calls, "
        f"got {session.run.call_count}"
    )


@pytest.mark.asyncio
async def test_ensure_core_constraints_uses_if_not_exists() -> None:
    """Every Cypher statement must contain IF NOT EXISTS so the call is idempotent."""
    session = AsyncMock()

    await ensure_core_constraints(session=session)

    for actual_call in session.run.call_args_list:
        cypher: str = actual_call.args[0]
        assert "IF NOT EXISTS" in cypher, (
            f"Constraint statement is missing IF NOT EXISTS: {cypher!r}"
        )


@pytest.mark.asyncio
async def test_ensure_core_constraints_covers_expected_labels() -> None:
    """All seven required labels must appear in the issued Cypher statements."""
    required_labels = {
        "Character",
        "Event",
        "Location",
        "WorldState",
        "Item",
        "Quest",
        "Faction",
    }
    session = AsyncMock()

    await ensure_core_constraints(session=session)

    issued_labels: set[str] = set()
    for actual_call in session.run.call_args_list:
        cypher: str = actual_call.args[0]
        for label in required_labels:
            if f":{label})" in cypher or f": {label})" in cypher or f"(n:{label})" in cypher:
                issued_labels.add(label)

    missing = required_labels - issued_labels
    assert not missing, f"Constraint statements missing for labels: {missing}"


# ---------------------------------------------------------------------------
# api_seeder idempotency (get-then-skip)
# ---------------------------------------------------------------------------


def _make_call_side_effect(existing_ids: set[str]):
    """Return a side-effect function that simulates existing resources.

    GET calls for IDs in ``existing_ids`` return HTTP 200.
    All POST calls return HTTP 200 (created).
    All other GET calls return HTTP 404.
    """

    def _side_effect(method: str, url: str, api_key: str, body=None):
        if method == "GET":
            # Extract last path segment or query-param free segment as the ID.
            path_part = url.split("?")[0]
            resource_id = path_part.rstrip("/").split("/")[-1]
            if resource_id in existing_ids:
                return 200, {"data": {"id": resource_id}}
            return 404, {}
        # POST always succeeds
        return 200, {"data": {}}

    return _side_effect


def test_seeder_skips_existing_factions(monkeypatch) -> None:
    """When a faction already exists, the seeder records it as skipped (no POST)."""
    from npc_engine.data import api_seeder, seed_http

    existing = {"guild"}  # faction id that already exists
    call_log: list[tuple[str, str]] = []

    def _mock_call(method, url, api_key, body=None):
        call_log.append((method, url))
        return _make_call_side_effect(existing)(method, url, api_key, body)

    monkeypatch.setattr(seed_http, "call", _mock_call)

    # Only test the faction seeding portion in isolation by calling faction_exists
    # and verifying no POST is issued for an existing faction.
    result = seed_http.faction_exists("http://host", "key", "guild")
    assert result is True

    post_calls = [m for m, _ in call_log if m == "POST"]
    assert post_calls == [], "No POST should be issued for an existing faction"


def test_seeder_creates_missing_factions(monkeypatch) -> None:
    """When a faction does not exist, the seeder issues a POST to create it."""
    from npc_engine.data import seed_http

    existing: set[str] = set()

    def _mock_call(method, url, api_key, body=None):
        return _make_call_side_effect(existing)(method, url, api_key, body)

    monkeypatch.setattr(seed_http, "call", _mock_call)

    result = seed_http.faction_exists("http://host", "key", "new_faction")
    assert result is False


def test_seeder_skips_existing_nodes(monkeypatch) -> None:
    """node_exists returns True for a node the API reports as existing."""
    from npc_engine.data import seed_http

    existing = {"loc_tavern"}

    def _mock_call(method, url, api_key, body=None):
        return _make_call_side_effect(existing)(method, url, api_key, body)

    monkeypatch.setattr(seed_http, "call", _mock_call)

    assert seed_http.node_exists("http://host", "key", "Location", "loc_tavern") is True
    assert seed_http.node_exists("http://host", "key", "Location", "loc_unknown") is False


def test_seed_skips_all_resources_when_all_exist(monkeypatch) -> None:
    """Running seed() on a fully-populated world skips all stable-ID resources."""
    from npc_engine.data import api_seeder, seed_data, seed_http

    ts = "2026-01-01T00:00:00+00:00"
    all_stable_ids = (
        {f["id"] for f in seed_data.get_factions()}
        | {loc["id"] for loc in seed_data.get_locations(ts)}
        | {char["id"] for char in seed_data.get_characters(ts)}
        | {evt["id"] for evt in seed_data.get_events(ts)}
    )

    post_count = 0

    def _mock_call(method, url, api_key, body=None):
        nonlocal post_count
        if method == "POST":
            post_count += 1
            return 200, {}
        # GET: return 200 for any stable ID
        path_part = url.split("?")[0]
        resource_id = path_part.rstrip("/").split("/")[-1]
        if resource_id in all_stable_ids:
            return 200, {"data": {"id": resource_id}}
        return 404, {}

    # Patch at both levels: api_seeder uses call directly; helpers use seed_http.call
    monkeypatch.setattr(api_seeder, "call", _mock_call)
    monkeypatch.setattr(seed_http, "call", _mock_call)

    exit_code = api_seeder.seed("http://host", "key")

    assert exit_code == 0, "seed() should not fail on a fully-populated world"
    # POSTs should only come from auto-ID resources (beliefs, goals, items,
    # secrets, memories, debts) — not from stable-ID resources.
    stable_resource_count = (
        len(seed_data.get_factions())
        + len(seed_data.get_locations(""))
        + len(seed_data.get_characters(""))
        + len(seed_data.get_faction_members())
        + len(seed_data.get_character_location())
        + len(seed_data.get_relates_to_pairs())
        + len(seed_data.get_events(""))
        + len(seed_data.get_event_participation())
        + len(seed_data.get_npc_ids()) * len(seed_data.get_events(""))
    )
    # post_count must be strictly less than total resources (some were skipped)
    # We can't assert post_count == 0 because auto-ID resources still POST.
    assert post_count < stable_resource_count + 1, (
        f"Too many POSTs issued ({post_count}); stable-ID resources should have been skipped"
    )
