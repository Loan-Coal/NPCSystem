"""
Module: test_h0_client_methods
Layer: demo_game (tests)
Purpose: Unit tests for Phase H0 EngineClient additions:
         break_pledge (H0.1), create_treaty / get_faction_treaties / break_treaty (H0.2),
         get_investigation (H0.3), get_current_chapter (H0.4), post_quest_choice (H0.5).
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
# H0.1 — break_pledge
# ---------------------------------------------------------------------------


class TestBreakPledge:
    """Tests for EngineClient.break_pledge."""

    def test_posts_to_correct_path(self) -> None:
        """Uses POST /v1/admin/pledges/characters/{id}/break."""
        m = MagicMock()
        m.post.return_value = _resp(200, {"data": {"broken": True}})
        _client(m).break_pledge("npc_a", "npc_b", "protect", 10)
        url = m.post.call_args[0][0]
        assert "/v1/admin/pledges/characters/npc_a/break" in url

    def test_sends_correct_body(self) -> None:
        """Sends pledgee_id, pledge_type, and tick in the JSON body."""
        m = MagicMock()
        m.post.return_value = _resp(200, {"data": {}})
        _client(m).break_pledge("npc_a", "npc_b", "fealty", 5)
        body = m.post.call_args[1]["json"]
        assert body["pledgee_id"] == "npc_b"
        assert body["pledge_type"] == "fealty"
        assert body["tick"] == 5

    def test_returns_response_dict(self) -> None:
        """Returns the full API response dict on success."""
        m = MagicMock()
        payload = {"data": {"broken": True, "pledger_id": "npc_a"}}
        m.post.return_value = _resp(200, payload)
        result = _client(m).break_pledge("npc_a", "npc_b", "protect", 1)
        assert result == payload

    def test_raises_on_400(self) -> None:
        """Raises EngineClientError on 4xx responses."""
        m = MagicMock()
        m.post.return_value = _resp(404, {"error": {"message": "not found"}})
        with pytest.raises(EngineClientError):
            _client(m).break_pledge("npc_a", "npc_b", "protect", 1)


# ---------------------------------------------------------------------------
# H0.2 — create_treaty
# ---------------------------------------------------------------------------


class TestCreateTreaty:
    """Tests for EngineClient.create_treaty."""

    def test_posts_to_treaties_endpoint(self) -> None:
        """Uses POST /v1/admin/treaties/."""
        m = MagicMock()
        m.post.return_value = _resp(200, {"data": {"treaty_id": "t1"}})
        _client(m).create_treaty(["faction_a", "faction_b"], "peace", 10)
        url = m.post.call_args[0][0]
        assert "/v1/admin/treaties/" in url

    def test_sends_parties_and_terms(self) -> None:
        """Sends parties, terms_narrative, and signed_at_tick."""
        m = MagicMock()
        m.post.return_value = _resp(200, {"data": {}})
        _client(m).create_treaty(["f1", "f2"], "non-aggression pact", 20)
        body = m.post.call_args[1]["json"]
        assert body["parties"] == ["f1", "f2"]
        assert body["terms_narrative"] == "non-aggression pact"
        assert body["signed_at_tick"] == 20

    def test_includes_expires_at_tick_when_given(self) -> None:
        """expires_at_tick is included when provided."""
        m = MagicMock()
        m.post.return_value = _resp(200, {"data": {}})
        _client(m).create_treaty(["f1", "f2"], "trade deal", 5, expires_at_tick=100)
        body = m.post.call_args[1]["json"]
        assert body["expires_at_tick"] == 100

    def test_raises_on_error(self) -> None:
        """Raises EngineClientError on 5xx."""
        m = MagicMock()
        m.post.return_value = _resp(500, {})
        with pytest.raises(EngineClientError):
            _client(m).create_treaty(["f1", "f2"], "x", 1)


# ---------------------------------------------------------------------------
# H0.2 — get_faction_treaties
# ---------------------------------------------------------------------------


class TestGetFactionTreaties:
    """Tests for EngineClient.get_faction_treaties."""

    def test_returns_treaties_list(self) -> None:
        """Returns treaties list from the data envelope."""
        m = MagicMock()
        treaties = [{"treaty_id": "t1", "status": "active"}]
        m.get.return_value = _resp(200, {"data": {"treaties": treaties}})
        result = _client(m).get_faction_treaties("faction_a")
        assert result == treaties

    def test_returns_empty_on_404(self) -> None:
        """Returns [] on 404 (graceful degrade)."""
        m = MagicMock()
        m.get.return_value = _resp(404, {})
        assert _client(m).get_faction_treaties("faction_a") == []

    def test_returns_empty_on_500(self) -> None:
        """Returns [] on 500 (graceful degrade)."""
        m = MagicMock()
        m.get.return_value = _resp(500, {})
        assert _client(m).get_faction_treaties("faction_a") == []

    def test_calls_correct_url(self) -> None:
        """Uses GET /v1/admin/treaties/factions/{faction_id}."""
        m = MagicMock()
        m.get.return_value = _resp(200, {"data": {"treaties": []}})
        _client(m).get_faction_treaties("thieves_guild")
        url = m.get.call_args[0][0]
        assert "thieves_guild" in url
        assert "treaties/factions" in url


# ---------------------------------------------------------------------------
# H0.2 — break_treaty
# ---------------------------------------------------------------------------


class TestBreakTreaty:
    """Tests for EngineClient.break_treaty."""

    def test_posts_to_correct_path(self) -> None:
        """Uses POST /v1/admin/treaties/{treaty_id}/break."""
        m = MagicMock()
        m.post.return_value = _resp(200, {"data": {}})
        _client(m).break_treaty("t1", "faction_a", 15)
        url = m.post.call_args[0][0]
        assert "/v1/admin/treaties/t1/break" in url

    def test_sends_correct_body(self) -> None:
        """Sends breaking_faction_id and tick."""
        m = MagicMock()
        m.post.return_value = _resp(200, {"data": {}})
        _client(m).break_treaty("t1", "faction_b", 20)
        body = m.post.call_args[1]["json"]
        assert body["breaking_faction_id"] == "faction_b"
        assert body["tick"] == 20

    def test_raises_on_error(self) -> None:
        """Raises EngineClientError on 4xx."""
        m = MagicMock()
        m.post.return_value = _resp(404, {"error": {"message": "not found"}})
        with pytest.raises(EngineClientError):
            _client(m).break_treaty("t1", "faction_a", 5)


# ---------------------------------------------------------------------------
# H0.3 — get_investigation
# ---------------------------------------------------------------------------


class TestGetInvestigation:
    """Tests for EngineClient.get_investigation."""

    def test_returns_context_on_200(self) -> None:
        """Returns the data dict from the envelope on 200."""
        m = MagicMock()
        ctx = {"evidence": [], "witnesses": [], "suspects": [], "deductions": [],
               "alibi_contradictions": [], "rumor_contradictions": []}
        m.get.return_value = _resp(200, {"data": ctx})
        result = _client(m).get_investigation("detective_1", "event_42")
        assert result == ctx

    def test_returns_none_on_404(self) -> None:
        """Returns None on 404."""
        m = MagicMock()
        m.get.return_value = _resp(404, {})
        assert _client(m).get_investigation("d1", "e1") is None

    def test_returns_none_on_500(self) -> None:
        """Returns None on 500 (graceful degrade)."""
        m = MagicMock()
        m.get.return_value = _resp(500, {})
        assert _client(m).get_investigation("d1", "e1") is None

    def test_calls_correct_url(self) -> None:
        """Uses GET /v1/investigations/{investigator_id}/{event_id}."""
        m = MagicMock()
        m.get.return_value = _resp(200, {"data": {}})
        _client(m).get_investigation("sherlock", "crime_001")
        url = m.get.call_args[0][0]
        assert "investigations/sherlock/crime_001" in url


# ---------------------------------------------------------------------------
# H0.4 — get_current_chapter
# ---------------------------------------------------------------------------


class TestGetCurrentChapter:
    """Tests for EngineClient.get_current_chapter."""

    def test_returns_chapter_on_200(self) -> None:
        """Returns the data dict from the envelope on 200."""
        m = MagicMock()
        chapter = {"id": "chap_1", "name": "Act I", "started_at_tick": 0,
                   "theme": "conflict", "status": "open"}
        m.get.return_value = _resp(200, {"data": chapter})
        result = _client(m).get_current_chapter()
        assert result == chapter

    def test_returns_none_on_404(self) -> None:
        """Returns None when no chapter is open."""
        m = MagicMock()
        m.get.return_value = _resp(404, {})
        assert _client(m).get_current_chapter() is None

    def test_returns_none_on_500(self) -> None:
        """Returns None on 500."""
        m = MagicMock()
        m.get.return_value = _resp(500, {})
        assert _client(m).get_current_chapter() is None

    def test_calls_correct_url(self) -> None:
        """Uses GET /v1/chapters/current."""
        m = MagicMock()
        m.get.return_value = _resp(200, {"data": {}})
        _client(m).get_current_chapter()
        url = m.get.call_args[0][0]
        assert "chapters/current" in url


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
