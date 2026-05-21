"""
Module: test_client
Layer: demo_game (tests)
Purpose: TDD unit tests for EngineClient — all 8 methods, happy path + error path.
Dependencies: demo_game.client, unittest.mock (no network, no engine required)
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClient, EngineClientError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(mock_http: MagicMock) -> EngineClient:
    """Build an EngineClient with an injected mock HTTP client."""
    return EngineClient("http://test", "secret", _http_client=mock_http)


# ---------------------------------------------------------------------------
# post_dialogue
# ---------------------------------------------------------------------------


def test_post_dialogue_success(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(200, {"data": {"npc_response": "Hello"}})
    result = _client(mock_http).post_dialogue("player_1", "npc_1", "Hi")
    assert result == {"data": {"npc_response": "Hello"}}
    mock_http.post.assert_called_once_with(
        "/v1/dialogue",
        json={
            "player_id": "player_1",
            "npc_id": "npc_1",
            "player_message": "Hi",
            "location_id": None,
            "session_id": None,
            "explicit_node_ids": [],
        },
        timeout=120.0,
    )


def test_post_dialogue_passes_optional_fields(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(200, {"data": {}})
    _client(mock_http).post_dialogue(
        "p", "n", "msg",
        location_id="loc_1",
        session_id="sess_1",
        explicit_node_ids=("node_a", "node_b"),
    )
    _, kwargs = mock_http.post.call_args
    assert kwargs["json"]["location_id"] == "loc_1"
    assert kwargs["json"]["session_id"] == "sess_1"
    assert kwargs["json"]["explicit_node_ids"] == ["node_a", "node_b"]


def test_post_dialogue_raises_on_http_error(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(500, {"error": "Internal"})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).post_dialogue("player_1", "npc_1", "Hi")


# ---------------------------------------------------------------------------
# get_graph_nodes
# ---------------------------------------------------------------------------


def test_get_graph_nodes_success(mock_http: MagicMock, make_response) -> None:
    nodes = [{"id": "npc_1", "properties": {}}]
    mock_http.get.return_value = make_response(200, {"data": nodes})
    result = _client(mock_http).get_graph_nodes("Character")
    assert result == nodes
    mock_http.get.assert_called_once_with(
        "/v1/graph/nodes/Character",
        params={"limit": 100, "offset": 0},
        timeout=15.0,
    )


def test_get_graph_nodes_raises_on_http_error(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(422, {"error": "bad type"})
    with pytest.raises(EngineClientError, match="HTTP 422"):
        _client(mock_http).get_graph_nodes("BadType")


# ---------------------------------------------------------------------------
# get_graph_edges
# ---------------------------------------------------------------------------


def test_get_graph_edges_success(mock_http: MagicMock, make_response) -> None:
    edges = [{"src_id": "npc_1", "dst_id": "event_1", "properties": {}}]
    mock_http.get.return_value = make_response(200, {"data": edges})
    result = _client(mock_http).get_graph_edges("KNOWS_ABOUT")
    assert result == edges
    mock_http.get.assert_called_once_with(
        "/v1/graph/edges/KNOWS_ABOUT",
        params={"limit": 100, "offset": 0},
        timeout=15.0,
    )


def test_get_graph_edges_with_filters(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(200, {"data": []})
    _client(mock_http).get_graph_edges("KNOWS_ABOUT", src_id="npc_1", dst_id="event_1")
    _, kwargs = mock_http.get.call_args
    assert kwargs["params"]["src_id"] == "npc_1"
    assert kwargs["params"]["dst_id"] == "event_1"


def test_get_graph_edges_raises_on_http_error(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(500, {})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).get_graph_edges("KNOWS_ABOUT")


# ---------------------------------------------------------------------------
# advance_clock
# ---------------------------------------------------------------------------


def test_advance_clock_success(mock_http: MagicMock, make_response) -> None:
    payload = {"data": {"current_tick": 5}}
    mock_http.post.return_value = make_response(200, payload)
    result = _client(mock_http).advance_clock(delta_ticks=2, game_time_seconds=60)
    assert result == payload
    mock_http.post.assert_called_once_with(
        "/v1/clock/advance",
        json={"delta_ticks": 2, "game_time_seconds": 60},
        timeout=15.0,
    )


def test_advance_clock_includes_time_field_when_given(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(200, {"data": {}})
    _client(mock_http).advance_clock(advance_time_field="day")
    _, kwargs = mock_http.post.call_args
    assert kwargs["json"]["advance_time_field"] == "day"


def test_advance_clock_raises_on_http_error(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(400, {"error": "bad mode"})
    with pytest.raises(EngineClientError, match="HTTP 400"):
        _client(mock_http).advance_clock()


# ---------------------------------------------------------------------------
# get_clock_state
# ---------------------------------------------------------------------------


def test_get_clock_state_success(mock_http: MagicMock, make_response) -> None:
    payload = {"data": {"current_tick": 3, "next_gossip_tick": 5}}
    mock_http.get.return_value = make_response(200, payload)
    result = _client(mock_http).get_clock_state()
    assert result == payload
    mock_http.get.assert_called_once_with("/v1/clock/state", timeout=15.0)


def test_get_clock_state_raises_on_http_error(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(503, {})
    with pytest.raises(EngineClientError, match="HTTP 503"):
        _client(mock_http).get_clock_state()


# ---------------------------------------------------------------------------
# get_npc_state
# ---------------------------------------------------------------------------


def test_get_npc_state_success(mock_http: MagicMock, make_response) -> None:
    payload = {"data": {"character": {"id": "npc_1"}, "relations": [], "events": []}}
    mock_http.get.return_value = make_response(200, payload)
    result = _client(mock_http).get_npc_state("npc_1")
    assert result == payload
    mock_http.get.assert_called_once_with("/v1/npc/npc_1/state", timeout=15.0)


def test_get_npc_state_raises_on_http_error(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(404, {"error": "not found"})
    with pytest.raises(EngineClientError, match="HTTP 404"):
        _client(mock_http).get_npc_state("npc_missing")


# ---------------------------------------------------------------------------
# get_world_state
# ---------------------------------------------------------------------------


def test_get_world_state_returns_first_item(mock_http: MagicMock, make_response) -> None:
    node = {"id": "ws_1", "properties": {"epoch": "peace"}}
    mock_http.get.return_value = make_response(200, {"data": [node]})
    result = _client(mock_http).get_world_state()
    assert result == node
    mock_http.get.assert_called_once_with(
        "/v1/graph/nodes/world_state",
        params={"limit": 1, "offset": 0},
        timeout=15.0,
    )


def test_get_world_state_returns_none_when_empty(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(200, {"data": []})
    assert _client(mock_http).get_world_state() is None


def test_get_world_state_raises_on_http_error(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(500, {})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).get_world_state()


# ---------------------------------------------------------------------------
# get_npc_reputation
# ---------------------------------------------------------------------------


def test_get_npc_reputation_success(mock_http: MagicMock, make_response) -> None:
    standings = [{"faction_id": "guard", "standing": 50}]
    mock_http.get.return_value = make_response(200, {"data": standings})
    result = _client(mock_http).get_npc_reputation("npc_2")
    assert result == standings
    mock_http.get.assert_called_once_with(
        "/v1/graph/characters/npc_2/reputation",
        timeout=15.0,
    )


def test_get_npc_reputation_raises_on_http_error(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(404, {"error": "not found"})
    with pytest.raises(EngineClientError, match="HTTP 404"):
        _client(mock_http).get_npc_reputation("npc_missing")
