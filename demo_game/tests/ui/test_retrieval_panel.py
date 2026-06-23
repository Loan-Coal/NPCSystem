"""
Module: test_retrieval_panel
Layer: demo_game (tests)
Purpose: Unit tests for RetrievalPanelWidget state setters, draw guard,
         and EngineClient.get_retrieval_debug wrapper.
         No pygame display init required — Surface and Rect are mocked.
Dependencies: demo_game.ui.retrieval_panel, demo_game.client, unittest.mock
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
    from demo_game.ui.panels.retrieval_panel import RetrievalPanelWidget
    return RetrievalPanelWidget(_MockFont(), _MockFont())


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


_SAMPLE_ITEMS = [
    {"key": "identity", "tier": "unknown", "priority": 0, "text": "Mira the innkeeper."},
    {"key": "recent_events", "tier": "unknown", "priority": 0, "text": "A war started."},
    {"key": "relationship", "tier": "unknown", "priority": 0, "text": "Trusts the player."},
]

_SAMPLE_PAYLOAD = {
    "npc_id": "mira_innkeeper",
    "query": "What do you know?",
    "context_items": _SAMPLE_ITEMS,
    "total_tokens": 42,
}


# ---------------------------------------------------------------------------
# RetrievalPanelWidget — initial state
# ---------------------------------------------------------------------------


def test_initial_items_empty() -> None:
    """Widget starts with no items."""
    w = _make_widget()
    assert w._items == []


def test_initial_total_tokens_zero() -> None:
    """Widget starts with zero token count."""
    w = _make_widget()
    assert w._total_tokens == 0


# ---------------------------------------------------------------------------
# set_payload
# ---------------------------------------------------------------------------


def test_set_payload_stores_items() -> None:
    """set_payload extracts the context_items list."""
    w = _make_widget()
    w.set_payload(_SAMPLE_PAYLOAD)
    assert len(w._items) == 3


def test_set_payload_stores_total_tokens() -> None:
    """set_payload stores total_tokens from the response."""
    w = _make_widget()
    w.set_payload(_SAMPLE_PAYLOAD)
    assert w._total_tokens == 42


def test_set_payload_empty_clears_items() -> None:
    """set_payload with None clears stored items."""
    w = _make_widget()
    w.set_payload(_SAMPLE_PAYLOAD)
    w.set_payload(None)
    assert w._items == []


def test_set_payload_empty_dict_graceful() -> None:
    """set_payload with {} does not crash and sets empty items."""
    w = _make_widget()
    w.set_payload({})
    assert w._items == []


# ---------------------------------------------------------------------------
# draw — renders item keys
# ---------------------------------------------------------------------------


def test_draw_renders_item_keys() -> None:
    """draw() renders each item key in the panel."""
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

    from demo_game.ui.panels.retrieval_panel import RetrievalPanelWidget
    w = RetrievalPanelWidget(_CapturingFont(), _CapturingFont())
    w.set_payload(_SAMPLE_PAYLOAD)

    with patch("demo_game.ui.panels.retrieval_panel.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)

    joined = " ".join(rendered_texts)
    assert "identity" in joined, "item key 'identity' should appear in rendered text"
    assert "recent_events" in joined, "item key 'recent_events' should appear"
    assert "relationship" in joined, "item key 'relationship' should appear"


def test_draw_renders_token_count() -> None:
    """draw() renders the total_tokens value."""
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

    from demo_game.ui.panels.retrieval_panel import RetrievalPanelWidget
    w = RetrievalPanelWidget(_CapturingFont(), _CapturingFont())
    w.set_payload(_SAMPLE_PAYLOAD)

    with patch("demo_game.ui.panels.retrieval_panel.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)

    joined = " ".join(rendered_texts)
    assert "42" in joined, "total_tokens=42 should appear in rendered text"


def test_draw_no_data_does_not_crash() -> None:
    """draw() with no items renders gracefully (empty-state hint)."""
    with patch("demo_game.ui.panels.retrieval_panel.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        w = _make_widget()
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)  # should not raise


def test_draw_fills_background() -> None:
    """draw() calls pygame.draw.rect for background fill."""
    with patch("demo_game.ui.panels.retrieval_panel.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        w = _make_widget()
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)
        mock_pygame.draw.rect.assert_called()


# ---------------------------------------------------------------------------
# EngineClient.get_retrieval_debug
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


def test_get_retrieval_debug_returns_payload() -> None:
    """get_retrieval_debug returns the parsed JSON dict on 200."""
    http = MagicMock()
    http.get.return_value = _make_response(200, _SAMPLE_PAYLOAD)
    client = _make_client(http)
    result = client.get_retrieval_debug("mira_innkeeper", "What do you know?")
    assert result is not None
    assert result["npc_id"] == "mira_innkeeper"
    assert len(result["context_items"]) == 3


def test_get_retrieval_debug_calls_correct_path() -> None:
    """get_retrieval_debug calls GET /v1/admin/debug/retrieval with correct params."""
    http = MagicMock()
    http.get.return_value = _make_response(200, _SAMPLE_PAYLOAD)
    client = _make_client(http)
    client.get_retrieval_debug("captain_sorn", "Tell me about the war")

    call_args = http.get.call_args
    path = call_args[0][0]
    params = call_args[1].get("params", {})
    assert "/v1/admin/debug/retrieval" in path
    assert params.get("npc_id") == "captain_sorn"
    assert params.get("query") == "Tell me about the war"


def test_get_retrieval_debug_returns_none_on_non_200() -> None:
    """get_retrieval_debug returns None on non-200 (graceful, no crash)."""
    http = MagicMock()
    http.get.return_value = _make_response(503, {"error": {"message": "unavailable"}})
    client = _make_client(http)
    result = client.get_retrieval_debug("mira_innkeeper", "hello")
    assert result is None


def test_get_retrieval_debug_returns_none_on_404() -> None:
    """get_retrieval_debug returns None on 404."""
    http = MagicMock()
    http.get.return_value = _make_response(404, {"error": {"message": "not found"}})
    client = _make_client(http)
    result = client.get_retrieval_debug("unknown_npc", "hello")
    assert result is None


def test_get_retrieval_debug_empty_items_graceful() -> None:
    """get_retrieval_debug handles an empty context_items list without crash."""
    payload = {
        "npc_id": "mira_innkeeper",
        "query": "hello",
        "context_items": [],
        "total_tokens": 0,
    }
    http = MagicMock()
    http.get.return_value = _make_response(200, payload)
    client = _make_client(http)
    result = client.get_retrieval_debug("mira_innkeeper", "hello")
    assert result is not None
    assert result["context_items"] == []


# ---------------------------------------------------------------------------
# RightPanel.RETRIEVAL enum value
# ---------------------------------------------------------------------------


def test_right_panel_has_retrieval_tab() -> None:
    """RightPanel enum includes a RETRIEVAL tab."""
    from demo_game.ui.layout.right_panel import RightPanel
    tab_values = {tab.value for tab in RightPanel}
    assert "RETRIEVAL" in tab_values


def test_right_panel_retrieval_cycles() -> None:
    """RightPanel.RETRIEVAL is reachable via cycle_tab from MEMORY."""
    from demo_game.ui.layout.right_panel import RightPanel
    panels = list(RightPanel)
    assert RightPanel.RETRIEVAL in panels
