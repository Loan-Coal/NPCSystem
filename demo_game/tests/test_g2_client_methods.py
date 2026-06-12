"""
Module: test_g2_client_methods
Layer: demo_game (tests)
Purpose: Unit tests for G2 EngineClient additions:
         get_player_model (G2.1) and get_director_beats (G2.3).
         No network — all HTTP calls are mocked.
Dependencies: demo_game.client, unittest.mock
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClient


def _client(mock_http: MagicMock) -> EngineClient:
    """Build an EngineClient with an injected mock HTTP client."""
    return EngineClient("http://test", "secret", _http_client=mock_http)


def _make_response(status_code: int, body: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = str(body)
    return resp


# ---------------------------------------------------------------------------
# get_player_model
# ---------------------------------------------------------------------------


class TestGetPlayerModel:
    """Tests for EngineClient.get_player_model."""

    def test_returns_data_on_200(self) -> None:
        """On 200 returns the data dict from the response envelope."""
        mock_http = MagicMock()
        data = {
            "npc_id": "mira_innkeeper",
            "player_id": "player_demo",
            "perceived_trust": 65,
            "perceived_intent": "friendly",
            "last_updated_at": "2025-01-01T00:00:00Z",
        }
        mock_http.get.return_value = _make_response(200, {"data": data})
        result = _client(mock_http).get_player_model("mira_innkeeper", "player_demo")
        assert result == data

    def test_returns_none_on_404(self) -> None:
        """On 404 (NPC has no model yet) returns None."""
        mock_http = MagicMock()
        mock_http.get.return_value = _make_response(404, {"detail": "not found"})
        result = _client(mock_http).get_player_model("mira_innkeeper", "player_demo")
        assert result is None

    def test_returns_none_on_500(self) -> None:
        """On 500 returns None (degrade gracefully)."""
        mock_http = MagicMock()
        mock_http.get.return_value = _make_response(500, {})
        result = _client(mock_http).get_player_model("captain_sorn", "player_demo")
        assert result is None

    def test_calls_correct_url(self) -> None:
        """Uses the correct REST path with npc_id and player_id interpolated."""
        mock_http = MagicMock()
        mock_http.get.return_value = _make_response(200, {"data": {}})
        _client(mock_http).get_player_model("aldric_merchant", "player_demo")
        call_url = mock_http.get.call_args[0][0]
        assert "aldric_merchant" in call_url
        assert "player_demo" in call_url
        assert "player-model" in call_url


# ---------------------------------------------------------------------------
# get_director_beats
# ---------------------------------------------------------------------------


class TestGetDirectorBeats:
    """Tests for EngineClient.get_director_beats."""

    def test_returns_list_on_200(self) -> None:
        """On 200 returns the JSON list directly."""
        mock_http = MagicMock()
        beats = [
            {"beat_kind": "tension_spike", "reason": "war", "npc_id": "mira_innkeeper",
             "player_id": "player_demo", "tick": 10},
        ]
        mock_http.get.return_value = _make_response(200, beats)
        result = _client(mock_http).get_director_beats(limit=5)
        assert result == beats

    def test_returns_empty_list_on_404(self) -> None:
        """On 404 returns empty list (graceful degrade)."""
        mock_http = MagicMock()
        mock_http.get.return_value = _make_response(404, {})
        result = _client(mock_http).get_director_beats()
        assert result == []

    def test_returns_empty_list_on_500(self) -> None:
        """On 500 returns empty list."""
        mock_http = MagicMock()
        mock_http.get.return_value = _make_response(500, {})
        result = _client(mock_http).get_director_beats()
        assert result == []

    def test_returns_empty_when_non_list_body(self) -> None:
        """When 2xx body is not a list (unexpected format) returns empty list."""
        mock_http = MagicMock()
        mock_http.get.return_value = _make_response(200, {"data": []})
        result = _client(mock_http).get_director_beats()
        assert result == []

    def test_passes_limit_param(self) -> None:
        """Passes limit as a query parameter."""
        mock_http = MagicMock()
        mock_http.get.return_value = _make_response(200, [])
        _client(mock_http).get_director_beats(limit=3)
        call_params = mock_http.get.call_args[1]["params"]
        assert call_params.get("limit") == 3
