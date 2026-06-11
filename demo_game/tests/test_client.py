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


# ---------------------------------------------------------------------------
# get_node
# ---------------------------------------------------------------------------


def test_get_node_returns_data_on_200(mock_http: MagicMock, make_response) -> None:
    node = {"id": "loc_tavern", "name": "The Rusty Flagon"}
    mock_http.get.return_value = make_response(200, {"data": node})
    result = _client(mock_http).get_node("Location", "loc_tavern")
    assert result == node
    mock_http.get.assert_called_once_with(
        "/v1/graph/nodes/Location/loc_tavern",
        timeout=15.0,
    )


def test_get_node_returns_none_on_404(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(404, {"error": "not found"})
    assert _client(mock_http).get_node("Location", "loc_missing") is None


def test_get_node_raises_on_500(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(500, {})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).get_node("Location", "loc_tavern")


# ---------------------------------------------------------------------------
# get_edge
# ---------------------------------------------------------------------------


def test_get_edge_returns_data_on_200(mock_http: MagicMock, make_response) -> None:
    edge = {"src_id": "npc_1", "dst_id": "npc_2", "standing": 70.0}
    mock_http.get.return_value = make_response(200, {"data": edge})
    result = _client(mock_http).get_edge("STANDS_WITH", "npc_1", "npc_2")
    assert result == edge
    mock_http.get.assert_called_once_with(
        "/v1/graph/edges/STANDS_WITH/npc_1/npc_2",
        timeout=15.0,
    )


def test_get_edge_returns_none_on_404(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(404, {"error": "not found"})
    assert _client(mock_http).get_edge("STANDS_WITH", "npc_1", "npc_2") is None


def test_get_edge_raises_on_500(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(500, {})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).get_edge("STANDS_WITH", "npc_1", "npc_2")


# ---------------------------------------------------------------------------
# upsert_node
# ---------------------------------------------------------------------------


def test_upsert_node_success(mock_http: MagicMock, make_response) -> None:
    node = {"id": "loc_tavern", "name": "The Rusty Flagon"}
    mock_http.post.return_value = make_response(200, {"data": node})
    result = _client(mock_http).upsert_node("Location", {"id": "loc_tavern", "name": "The Rusty Flagon"})
    assert result == {"data": node}
    mock_http.post.assert_called_once_with(
        "/v1/graph/nodes/Location",
        json={"properties": {"id": "loc_tavern", "name": "The Rusty Flagon"}},
        timeout=15.0,
    )


def test_upsert_node_raises_on_422(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(422, {"error": "validation"})
    with pytest.raises(EngineClientError, match="HTTP 422"):
        _client(mock_http).upsert_node("Location", {})


# ---------------------------------------------------------------------------
# upsert_edge
# ---------------------------------------------------------------------------


def test_upsert_edge_success(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(200, {"data": {}})
    _client(mock_http).upsert_edge("STANDS_WITH", "npc_1", "npc_2", {"standing": 70.0})
    mock_http.post.assert_called_once_with(
        "/v1/graph/edges/STANDS_WITH",
        json={"src_id": "npc_1", "dst_id": "npc_2", "properties": {"standing": 70.0}},
        timeout=15.0,
    )


def test_upsert_edge_uses_empty_properties_when_none(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(200, {"data": {}})
    _client(mock_http).upsert_edge("KNOWS_ABOUT", "npc_1", "npc_2")
    _, kwargs = mock_http.post.call_args
    assert kwargs["json"]["properties"] == {}


def test_upsert_edge_raises_on_422(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(422, {"error": "validation"})
    with pytest.raises(EngineClientError, match="HTTP 422"):
        _client(mock_http).upsert_edge("STANDS_WITH", "a", "b")


# ---------------------------------------------------------------------------
# get_beliefs
# ---------------------------------------------------------------------------


def test_get_beliefs_returns_list(mock_http: MagicMock, make_response) -> None:
    beliefs = [{"id": "b_1", "content": "War is coming"}]
    mock_http.get.return_value = make_response(200, {"data": {"beliefs": beliefs}})
    result = _client(mock_http).get_beliefs("npc_1")
    assert result == beliefs
    mock_http.get.assert_called_once_with("/v1/admin/beliefs/npc_1", timeout=15.0)


def test_get_beliefs_returns_empty_list_when_none(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(200, {"data": {"beliefs": []}})
    assert _client(mock_http).get_beliefs("npc_1") == []


def test_get_beliefs_raises_on_500(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(500, {})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).get_beliefs("npc_1")


# ---------------------------------------------------------------------------
# post_belief
# ---------------------------------------------------------------------------

_GAME_TIME = {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}


def test_post_belief_success(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(201, {"belief_id": "b_1"})
    result = _client(mock_http).post_belief("npc_1", "War is coming", 80, _GAME_TIME)
    assert result == {"belief_id": "b_1"}
    mock_http.post.assert_called_once_with(
        "/v1/admin/beliefs/npc_1",
        json={"content": "War is coming", "confidence": 80, "game_time": _GAME_TIME},
        timeout=15.0,
    )


def test_post_belief_raises_on_422(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(422, {"error": "validation"})
    with pytest.raises(EngineClientError, match="HTTP 422"):
        _client(mock_http).post_belief("npc_1", "", 80, _GAME_TIME)


# ---------------------------------------------------------------------------
# post_goal
# ---------------------------------------------------------------------------


def test_post_goal_success(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(201, {"goal_id": "g_1"})
    result = _client(mock_http).post_goal("npc_1", "Catch the thief", 75, _GAME_TIME)
    assert result == {"goal_id": "g_1"}
    mock_http.post.assert_called_once_with(
        "/v1/admin/goals/npc_1",
        json={"description": "Catch the thief", "urgency": 75, "game_time": _GAME_TIME},
        timeout=15.0,
    )


def test_post_goal_includes_target_id_when_given(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(201, {"goal_id": "g_2"})
    _client(mock_http).post_goal("npc_1", "Find the ledger", 80, _GAME_TIME, target_id="npc_2")
    _, kwargs = mock_http.post.call_args
    assert kwargs["json"]["target_id"] == "npc_2"


def test_post_goal_raises_on_422(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(422, {"error": "validation"})
    with pytest.raises(EngineClientError, match="HTTP 422"):
        _client(mock_http).post_goal("npc_1", "", 75, _GAME_TIME)


# ---------------------------------------------------------------------------
# post_memory
# ---------------------------------------------------------------------------


def test_post_memory_success(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(201, {"memory_id": "m_1"})
    result = _client(mock_http).post_memory("npc_1", "I saw the fire", 85, 70, _GAME_TIME)
    assert result == {"memory_id": "m_1"}
    mock_http.post.assert_called_once_with(
        "/v1/admin/memories/npc_1",
        json={
            "content": "I saw the fire", "vividness": 85, "emotional_charge": 70,
            "game_time": _GAME_TIME, "is_historical": False,
        },
        timeout=15.0,
    )


def test_post_memory_historical_includes_occurred_at(mock_http: MagicMock, make_response) -> None:
    """A historical memory sends is_historical=True and an occurred_at_game_time (S26.3)."""
    mock_http.post.return_value = make_response(201, {"memory_id": "m_2"})
    occurred = {"year": 0, "season": "autumn", "day": 1, "time_of_day": "night"}
    _client(mock_http).post_memory(
        "npc_1", "the old war", 90, -50, _GAME_TIME,
        occurred_at_game_time=occurred, is_historical=True,
    )
    body = mock_http.post.call_args.kwargs["json"]
    assert body["is_historical"] is True
    assert body["occurred_at_game_time"] == occurred


def test_post_memory_raises_on_422(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(422, {"error": "validation"})
    with pytest.raises(EngineClientError, match="HTTP 422"):
        _client(mock_http).post_memory("npc_1", "", 85, 70, _GAME_TIME)


# ---------------------------------------------------------------------------
# post_secret
# ---------------------------------------------------------------------------


def test_post_secret_success(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(201, {"secret_id": "s_1"})
    result = _client(mock_http).post_secret("npc_1", "Hidden tunnel under the tavern", 75, _GAME_TIME)
    assert result == {"secret_id": "s_1"}
    mock_http.post.assert_called_once_with(
        "/v1/admin/secrets/npc_1",
        json={"content": "Hidden tunnel under the tavern", "severity": 75, "game_time": _GAME_TIME},
        timeout=15.0,
    )


def test_post_secret_raises_on_422(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(422, {"error": "validation"})
    with pytest.raises(EngineClientError, match="HTTP 422"):
        _client(mock_http).post_secret("npc_1", "", 75, _GAME_TIME)


# ---------------------------------------------------------------------------
# put_world_state
# ---------------------------------------------------------------------------


def test_put_world_state_success(mock_http: MagicMock, make_response) -> None:
    # L9-02: put_world_state PATCHes the canonical 'world' node (partial update),
    # it does not POST/upsert (which 422s on the existing node's required fields).
    mock_http.patch.return_value = make_response(200, {"data": {"id": "world", "epoch": "war"}})
    result = _client(mock_http).put_world_state("war", ["northern_war"])
    assert result["epoch"] == "war"
    args, kwargs = mock_http.patch.call_args
    assert args[0] == "/v1/graph/nodes/world_state/world"
    props = kwargs["json"]["properties"]
    assert "id" not in props, "id is the URL path segment, not a patched property"
    assert props["epoch"] == "war"
    assert props["active_conditions"] == ["northern_war"]
    assert "faction_standings" not in props and "weather" not in props


def test_put_world_state_raises_on_500(mock_http: MagicMock, make_response) -> None:
    mock_http.patch.return_value = make_response(500, {})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).put_world_state("war", [])


# ---------------------------------------------------------------------------
# put_npc_reputation
# ---------------------------------------------------------------------------


def test_put_npc_reputation_success(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(200, {"data": {}})
    _client(mock_http).put_npc_reputation("captain_sorn", "city_guard", 80)
    mock_http.post.assert_called_once_with(
        "/v1/graph/edges/STANDS_WITH",
        json={"src_id": "captain_sorn", "dst_id": "city_guard", "properties": {"standing": 80, "last_changed_at": "tick_0"}},
        timeout=15.0,
    )


def test_put_npc_reputation_raises_on_500(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(500, {})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).put_npc_reputation("captain_sorn", "city_guard", 80.0)


# ---------------------------------------------------------------------------
# get_npc_emotion
# ---------------------------------------------------------------------------


def test_get_npc_emotion_success(mock_http: MagicMock, make_response) -> None:
    payload = {"npc_id": "mira_innkeeper", "label": "happy", "valence": 0.6, "arousal": 0.4, "updated_at": "t0"}
    mock_http.get.return_value = make_response(200, payload)
    result = _client(mock_http).get_npc_emotion("mira_innkeeper")
    assert result == payload
    mock_http.get.assert_called_once_with("/v1/npc/mira_innkeeper/emotion", timeout=15.0)


def test_get_npc_emotion_returns_none_on_404(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(404, {"error": "not found"})
    assert _client(mock_http).get_npc_emotion("ghost_npc") is None


def test_get_npc_emotion_raises_on_500(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(500, {})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).get_npc_emotion("mira_innkeeper")


# ---------------------------------------------------------------------------
# post_quest_generate
# ---------------------------------------------------------------------------


def test_post_quest_generate_returns_data(mock_http: MagicMock, make_response) -> None:
    payload = {"quest_id": "q_001", "description": "Retrieve the northern spices."}
    mock_http.post.return_value = make_response(200, {"data": payload})
    result = _client(mock_http).post_quest_generate("aldric_merchant")
    assert result == payload
    mock_http.post.assert_called_once_with(
        "/v1/admin/quests/generate",
        json={"quest_giver_id": "aldric_merchant"},
        timeout=120.0,
    )


def test_post_quest_generate_raises_on_error(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(500, {"error": "LLM unavailable"})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).post_quest_generate("aldric_merchant")


# ---------------------------------------------------------------------------
# get_quest
# ---------------------------------------------------------------------------


def test_get_quest_returns_data_on_200(mock_http: MagicMock, make_response) -> None:
    quest = {"id": "q_001", "title": "Find the spices", "status": "available"}
    mock_http.get.return_value = make_response(200, {"data": {"quest": quest}})
    result = _client(mock_http).get_quest("q_001")
    assert result == quest
    mock_http.get.assert_called_once_with("/v1/admin/quests/q_001", timeout=15.0)


def test_get_quest_returns_none_on_404(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(404, {"error": "not found"})
    assert _client(mock_http).get_quest("missing_quest") is None


def test_get_quest_raises_on_500(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(500, {})
    with pytest.raises(EngineClientError, match="HTTP 500"):
        _client(mock_http).get_quest("q_001")


# ---------------------------------------------------------------------------
# get_item_price
# ---------------------------------------------------------------------------


def test_get_item_price_returns_price_on_200(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(200, {"data": {"price": 120}})
    result = _client(mock_http).get_item_price("spice", "aldric_merchant")
    assert result == 120
    mock_http.get.assert_called_once_with(
        "/v1/admin/economy/price",
        params={"item_type": "spice", "character_id": "aldric_merchant"},
        timeout=15.0,
    )


def test_get_item_price_returns_none_on_404(mock_http: MagicMock, make_response) -> None:
    mock_http.get.return_value = make_response(404, {})
    assert _client(mock_http).get_item_price("spice", "aldric_merchant") is None


# ---------------------------------------------------------------------------
# post_trade
# ---------------------------------------------------------------------------


def test_post_trade_returns_result_on_200(mock_http: MagicMock, make_response) -> None:
    payload = {"data": {"accepted": False, "rejection_reason": "price too low"}}
    mock_http.post.return_value = make_response(200, payload)
    result = _client(mock_http).post_trade(
        buyer_id="player",
        seller_id="aldric_merchant",
        item_id="northern_spice_bundle",
        item_type="spice",
        offered_price=80,
        tick=0,
    )
    assert result == payload
    _, kwargs = mock_http.post.call_args
    body = kwargs["json"]
    assert body["offered_price"] == 80
    assert body["seller_id"] == "aldric_merchant"


def test_post_trade_raises_on_4xx(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(422, {"detail": "invalid"})
    with pytest.raises(EngineClientError, match="HTTP 422"):
        _client(mock_http).post_trade(
            buyer_id="player",
            seller_id="aldric_merchant",
            item_id="northern_spice_bundle",
            item_type="spice",
            offered_price=80,
            tick=0,
        )


# ---------------------------------------------------------------------------
# _quest_headers
# ---------------------------------------------------------------------------


def test_quest_headers_hash_is_deterministic() -> None:
    """Same method + path + payload always produces the same hash."""
    c = _client(MagicMock())
    h1 = c._quest_headers("POST", "/v1/quests/offer", {"quest_id": "q1"})
    h2 = c._quest_headers("POST", "/v1/quests/offer", {"quest_id": "q1"})
    assert h1["X-Idempotency-Request-Hash"] == h2["X-Idempotency-Request-Hash"]


def test_quest_headers_request_id_differs_per_call() -> None:
    """X-Request-ID must be a fresh uuid4 on every call."""
    c = _client(MagicMock())
    h1 = c._quest_headers("POST", "/v1/quests/offer", {})
    h2 = c._quest_headers("POST", "/v1/quests/offer", {})
    assert h1["X-Request-ID"] != h2["X-Request-ID"]


def test_quest_headers_contains_all_required_keys() -> None:
    """All three X- headers must be present."""
    c = _client(MagicMock())
    headers = c._quest_headers("POST", "/v1/quests/accept", {"quest_id": "q1"})
    assert "X-Request-ID" in headers
    assert "X-Idempotency-Key" in headers
    assert "X-Idempotency-Request-Hash" in headers


# ---------------------------------------------------------------------------
# post_quest_offer
# ---------------------------------------------------------------------------


def test_post_quest_offer_success(mock_http: MagicMock, make_response) -> None:
    payload = {"data": {"quest_id": "q_001", "status": "offered"}}
    mock_http.post.return_value = make_response(200, payload)
    result = _client(mock_http).post_quest_offer(
        "q_001", "player", "Find the spices",
        objectives=[{"objective_id": "obj_1", "target_count": 1, "objective_type": "deliver", "target_id": "spice"}],
        item_rewards=[],
        currency_reward={"amount": 50},
    )
    assert result == payload
    _, kwargs = mock_http.post.call_args
    assert kwargs["json"]["quest_id"] == "q_001"
    assert "X-Idempotency-Request-Hash" in kwargs["headers"]


def test_post_quest_offer_raises_on_4xx(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(404, {"detail": "quest not found"})
    with pytest.raises(EngineClientError, match="HTTP 404"):
        _client(mock_http).post_quest_offer(
            "missing", "player", "title",
            objectives=[], item_rewards=[], currency_reward=None,
        )


# ---------------------------------------------------------------------------
# post_quest_accept
# ---------------------------------------------------------------------------


def test_post_quest_accept_success(mock_http: MagicMock, make_response) -> None:
    payload = {"data": {"quest_id": "q_001", "status": "active"}}
    mock_http.post.return_value = make_response(200, payload)
    result = _client(mock_http).post_quest_accept("q_001", "player")
    assert result == payload
    _, kwargs = mock_http.post.call_args
    assert kwargs["json"]["quest_id"] == "q_001"
    assert "X-Idempotency-Request-Hash" in kwargs["headers"]


def test_post_quest_accept_raises_on_4xx(mock_http: MagicMock, make_response) -> None:
    mock_http.post.return_value = make_response(409, {"detail": "already accepted"})
    with pytest.raises(EngineClientError, match="HTTP 409"):
        _client(mock_http).post_quest_accept("q_001", "player")


# ---------------------------------------------------------------------------
# pledges (ISSUE-061 path-drift regression — route is mounted at /v1/admin)
# ---------------------------------------------------------------------------


def test_post_pledge_uses_admin_path(mock_http: MagicMock, make_response) -> None:
    """post_pledge targets /v1/admin/pledges/... (pledges_router is under admin_prefix)."""
    mock_http.post.return_value = make_response(200, {"data": {}})
    _client(mock_http).post_pledge("lira_fence", "thieves_guild", "loyalty", 1)
    assert mock_http.post.call_args.args[0] == "/v1/admin/pledges/characters/lira_fence"


def test_get_pledges_for_npc_uses_admin_path(mock_http: MagicMock, make_response) -> None:
    """get_pledges_for_npc targets /v1/admin/pledges/... (was /v1/pledges → 404)."""
    mock_http.get.return_value = make_response(200, {"data": {"pledges": []}})
    _client(mock_http).get_pledges_for_npc("lira_fence")
    assert mock_http.get.call_args.args[0] == "/v1/admin/pledges/characters/lira_fence"
