"""
Module: test_faction_board
Layer: demo_game (tests)
Purpose: Unit tests for FactionBoardWidget (state setters, draw guard) and
         EngineClient.get_faction_standings (mock payload → rendered; empty → graceful).
         No pygame display init required — Surface and Rect are mocked.
Dependencies: demo_game.ui.faction_board, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _MockFont:
    """Minimal pygame Font stub for rendering tests."""

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * 7
        surf.get_height.return_value = 14
        return surf

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 7, 14)

    def get_linesize(self) -> int:
        return 14


def _make_widget():
    from demo_game.ui.faction_board import FactionBoardWidget
    return FactionBoardWidget(_MockFont(), _MockFont())


def _make_surface_rect() -> tuple[MagicMock, MagicMock]:
    surface = MagicMock()
    rect = MagicMock()
    rect.x = 0
    rect.y = 0
    rect.width = 400
    rect.height = 600
    rect.right = 400
    rect.bottom = 600
    rect.centerx = 200
    rect.centery = 300
    return surface, rect


_SAMPLE_STANDINGS = [
    {"faction_id": "merchants_guild", "faction_name": "Merchants Guild", "standing": 60},
    {"faction_id": "thieves_guild",   "faction_name": "Thieves Guild",   "standing": -20},
    {"faction_id": "city_guard",      "faction_name": "City Guard",      "standing": 80},
]


# ---------------------------------------------------------------------------
# FactionBoardWidget — initial state
# ---------------------------------------------------------------------------


def test_initial_standings_empty() -> None:
    """Widget starts with no standings entries."""
    w = _make_widget()
    assert w._standings == []


# ---------------------------------------------------------------------------
# set_standings
# ---------------------------------------------------------------------------


def test_set_standings_stores_entries() -> None:
    """set_standings stores the supplied list."""
    w = _make_widget()
    w.set_standings(_SAMPLE_STANDINGS)
    assert len(w._standings) == 3


def test_set_standings_with_empty_list() -> None:
    """set_standings with [] stores an empty list."""
    w = _make_widget()
    w.set_standings(_SAMPLE_STANDINGS)
    w.set_standings([])
    assert w._standings == []


def test_set_standings_with_none_clears() -> None:
    """set_standings with None degrades gracefully and clears standings."""
    w = _make_widget()
    w.set_standings(_SAMPLE_STANDINGS)
    w.set_standings(None)
    assert w._standings == []


# ---------------------------------------------------------------------------
# draw — renders faction names and standings
# ---------------------------------------------------------------------------


def test_draw_renders_faction_names() -> None:
    """draw() renders each faction name in the panel."""
    rendered_texts: list[str] = []

    class _CapturingFont:
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            surf = MagicMock()
            surf.get_width.return_value = len(text) * 7
            surf.get_height.return_value = 14
            return surf

        def size(self, text: str) -> tuple[int, int]:
            return (len(text) * 7, 14)

        def get_linesize(self) -> int:
            return 14

    from demo_game.ui.faction_board import FactionBoardWidget
    w = FactionBoardWidget(_CapturingFont(), _CapturingFont())
    w.set_standings(_SAMPLE_STANDINGS)

    with patch("demo_game.ui.faction_board.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)

    joined = " ".join(rendered_texts)
    assert "Merchants Guild" in joined
    assert "Thieves Guild" in joined
    assert "City Guard" in joined


def test_draw_renders_standing_values() -> None:
    """draw() renders standing numbers for each faction."""
    rendered_texts: list[str] = []

    class _CapturingFont:
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            surf = MagicMock()
            surf.get_width.return_value = len(text) * 7
            surf.get_height.return_value = 14
            return surf

        def size(self, text: str) -> tuple[int, int]:
            return (len(text) * 7, 14)

        def get_linesize(self) -> int:
            return 14

    from demo_game.ui.faction_board import FactionBoardWidget
    w = FactionBoardWidget(_CapturingFont(), _CapturingFont())
    w.set_standings(_SAMPLE_STANDINGS)

    with patch("demo_game.ui.faction_board.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)

    joined = " ".join(rendered_texts)
    assert "60" in joined
    assert "-20" in joined
    assert "80" in joined


def test_draw_no_data_does_not_crash() -> None:
    """draw() with no standings renders gracefully (empty-state hint)."""
    with patch("demo_game.ui.faction_board.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        w = _make_widget()
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)  # must not raise


def test_draw_fills_background() -> None:
    """draw() calls pygame.draw.rect for background fill."""
    with patch("demo_game.ui.faction_board.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        w = _make_widget()
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)
        mock_pygame.draw.rect.assert_called()


# ---------------------------------------------------------------------------
# EngineClient.get_faction_standings
# ---------------------------------------------------------------------------


def _make_client(http_mock: MagicMock) -> object:
    from demo_game.client import EngineClient
    return EngineClient(
        base_url="http://localhost:8000",
        api_key="test-key",
        _http_client=http_mock,
    )


def _make_response(status_code: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = str(body)
    return resp


_FACTIONS_LIST_BODY = {
    "data": [
        {"id": "merchants_guild", "name": "Merchants Guild", "archetype": "mercantile"},
        {"id": "thieves_guild",   "name": "Thieves Guild",   "archetype": "criminal"},
        {"id": "city_guard",      "name": "City Guard",      "archetype": "military"},
    ]
}

_STANDINGS_BODY_MG = {
    "data": [{"src_id": "merchants_guild", "dst_id": "thieves_guild", "standing": -30}]
}
_STANDINGS_BODY_TG = {"data": []}
_STANDINGS_BODY_CG = {
    "data": [{"src_id": "city_guard", "dst_id": "merchants_guild", "standing": 50}]
}


def test_get_faction_standings_returns_list() -> None:
    """get_faction_standings returns a list of standing dicts on 200."""
    http = MagicMock()
    # First call: list factions; subsequent calls: per-faction standings
    http.get.side_effect = [
        _make_response(200, _FACTIONS_LIST_BODY),
        _make_response(200, _STANDINGS_BODY_MG),
        _make_response(200, _STANDINGS_BODY_TG),
        _make_response(200, _STANDINGS_BODY_CG),
    ]
    client = _make_client(http)
    result = client.get_faction_standings()
    assert isinstance(result, list)


def test_get_faction_standings_returns_none_on_non_200() -> None:
    """get_faction_standings returns None when the factions list call fails."""
    http = MagicMock()
    http.get.return_value = _make_response(503, {"error": {"message": "unavailable"}})
    client = _make_client(http)
    result = client.get_faction_standings()
    assert result is None


def test_get_faction_standings_returns_none_on_404() -> None:
    """get_faction_standings returns None on 404."""
    http = MagicMock()
    http.get.return_value = _make_response(404, {"error": {"message": "not found"}})
    client = _make_client(http)
    result = client.get_faction_standings()
    assert result is None


def test_get_faction_standings_empty_graceful() -> None:
    """get_faction_standings returns an empty list when no factions exist."""
    http = MagicMock()
    http.get.return_value = _make_response(200, {"data": []})
    client = _make_client(http)
    result = client.get_faction_standings()
    assert result == []


def test_get_faction_standings_calls_correct_path() -> None:
    """get_faction_standings calls GET /v1/admin/factions/ to list factions."""
    http = MagicMock()
    http.get.return_value = _make_response(200, {"data": []})
    client = _make_client(http)
    client.get_faction_standings()
    call_path = http.get.call_args[0][0]
    assert "/v1/admin/factions" in call_path


# ---------------------------------------------------------------------------
# RightPanel.FACTION enum value
# ---------------------------------------------------------------------------


def test_right_panel_has_faction_tab() -> None:
    """RightPanel enum includes a FACTION tab."""
    from demo_game.ui.right_panel import RightPanel
    tab_values = {tab.value for tab in RightPanel}
    assert "FACTION" in tab_values


def test_right_panel_faction_cycles() -> None:
    """RightPanel.FACTION is reachable via cycle_tab traversal."""
    from demo_game.ui.right_panel import RightPanel
    panels = list(RightPanel)
    assert RightPanel.FACTION in panels
