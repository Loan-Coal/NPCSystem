"""
Module: test_h0_client_methods
Layer: demo_game (tests)
Purpose: Unit tests for Phase H0 EngineClient additions: post_quest_choice (H0.5).
         No network — all HTTP calls are mocked via unittest.mock.
Dependencies: demo_game.client, unittest.mock
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock

from demo_game.client import EngineClient, EngineClientError
import pytest


def _client(mock_http: MagicMock) -> EngineClient:
    """Build an EngineClient with an injected mock HTTP client."""
    return EngineClient("http://test", "secret", _http_client=mock_http)


def _resp(status: int, body: object) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    r.text = str(body)
    return r


# ---------------------------------------------------------------------------
# H0.5 — post_quest_choice
# ---------------------------------------------------------------------------


class TestPostQuestChoice:
    """Tests for EngineClient.post_quest_choice."""

    def test_posts_to_correct_path(self) -> None:
        """Uses POST /v1/quest/{quest_id}/choose."""
        m = MagicMock()
        m.post.return_value = _resp(200, {"data": {}})
        _client(m).post_quest_choice("quest_1", "choice_a", "player_1")
        url = m.post.call_args[0][0]
        assert "/v1/quest/quest_1/choose" in url

    def test_sends_correct_body(self) -> None:
        """Sends player_id and choice_id."""
        m = MagicMock()
        m.post.return_value = _resp(200, {"data": {}})
        _client(m).post_quest_choice("q1", "branch_b", "player_demo")
        body = m.post.call_args[1]["json"]
        assert body["player_id"] == "player_demo"
        assert body["choice_id"] == "branch_b"

    def test_returns_response_dict(self) -> None:
        """Returns full API response dict on success."""
        m = MagicMock()
        payload = {"data": {"quest_id": "q1", "player_id": "p1", "next_quest_id": "q2"}}
        m.post.return_value = _resp(200, payload)
        result = _client(m).post_quest_choice("q1", "c1", "p1")
        assert result == payload

    def test_raises_on_404(self) -> None:
        """Raises EngineClientError on 404 (quest not found)."""
        m = MagicMock()
        m.post.return_value = _resp(404, {"error": {"message": "quest not found"}})
        with pytest.raises(EngineClientError):
            _client(m).post_quest_choice("bad_id", "c1", "p1")
