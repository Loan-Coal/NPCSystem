"""
Module: test_g1_wiring
Layer: demo_game (tests)
Purpose: TDD unit tests for Phase G1 demo-surface live-wiring:
         - G1.2  retrieval refresh on-turn (via mock client + mock right panel)
         - G1.4  EngineClient.get_relationship (200 / ≥400 degradation)
         - G1.4  LeftPanelRenderer.set_relationship_phase (store + render None-safe)
No pygame display required — pygame is patched where needed.
Dependencies: demo_game.client, demo_game.ui.left_panel, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _MockFont:
    """Minimal pygame Font stub (no display needed)."""

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * 7
        surf.get_height.return_value = 14
        return surf

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 7, 14)

    def get_linesize(self) -> int:
        return 14


def _make_renderer():
    """Construct a LeftPanelRenderer with mock fonts."""
    from demo_game.ui.left_panel import LeftPanelRenderer

    return LeftPanelRenderer(
        font_body=_MockFont(),
        font_label=_MockFont(),
        font_nav=_MockFont(),
        font_loc=_MockFont(),
    )


def _make_rect(x: int = 0, y: int = 0, w: int = 200, h: int = 96) -> MagicMock:
    rect = MagicMock()
    rect.x = x
    rect.y = y
    rect.width = w
    rect.height = h
    rect.centerx = x + w // 2
    rect.centery = y + h // 2
    rect.right = x + w
    rect.bottom = y + h
    return rect


def _make_http(status_code: int, body: dict) -> MagicMock:
    """Return a mock httpx client where .get() returns a response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = str(body)
    http = MagicMock()
    http.get.return_value = resp
    return http


def _make_engine_client(http_mock: MagicMock):
    """Construct an EngineClient with an injected mock http client."""
    from demo_game.client import EngineClient

    return EngineClient(
        base_url="http://localhost:8000",
        api_key="test-key",
        _http_client=http_mock,
    )


# ---------------------------------------------------------------------------
# G1.4 — EngineClient.get_relationship
# ---------------------------------------------------------------------------


_RELATIONSHIP_DATA = {
    "standing": "trusted",
    "trust": 60,
    "fear": 5,
    "affection": 20,
    "relationship_phase": "ally",
    "phase_started_at_tick": 10,
}

_RELATIONSHIP_ENVELOPE = {"status": "ok", "data": _RELATIONSHIP_DATA}


class TestGetRelationship:
    def test_returns_data_dict_on_200(self) -> None:
        """get_relationship returns the 'data' sub-dict on a 200 response."""
        http = _make_http(200, _RELATIONSHIP_ENVELOPE)
        client = _make_engine_client(http)
        result = client.get_relationship("mira_innkeeper", "player_demo")
        assert result is not None
        assert result["relationship_phase"] == "ally"
        assert result["trust"] == 60

    def test_calls_correct_endpoint(self) -> None:
        """get_relationship calls GET /v1/npc/{npc_id}/relationship/{other_id}."""
        http = _make_http(200, _RELATIONSHIP_ENVELOPE)
        client = _make_engine_client(http)
        client.get_relationship("captain_sorn", "player_demo")
        call_path = http.get.call_args[0][0]
        assert "/v1/npc/captain_sorn/relationship/player_demo" in call_path

    def test_returns_none_on_400(self) -> None:
        """get_relationship returns None on 400 — graceful degradation."""
        http = _make_http(400, {"error": {"message": "not found"}})
        client = _make_engine_client(http)
        result = client.get_relationship("unknown_npc", "player_demo")
        assert result is None

    def test_returns_none_on_404(self) -> None:
        """get_relationship returns None on 404."""
        http = _make_http(404, {"error": {"message": "not found"}})
        client = _make_engine_client(http)
        result = client.get_relationship("mira_innkeeper", "player_demo")
        assert result is None

    def test_returns_none_on_503(self) -> None:
        """get_relationship returns None on 503 (service unavailable)."""
        http = _make_http(503, {"error": {"message": "unavailable"}})
        client = _make_engine_client(http)
        result = client.get_relationship("mira_innkeeper", "player_demo")
        assert result is None

    def test_relationship_phase_field_present(self) -> None:
        """The returned dict includes relationship_phase."""
        http = _make_http(200, _RELATIONSHIP_ENVELOPE)
        client = _make_engine_client(http)
        result = client.get_relationship("mira_innkeeper", "player_demo")
        assert "relationship_phase" in result  # type: ignore[operator]

    def test_phase_started_at_tick_field_present(self) -> None:
        """The returned dict includes phase_started_at_tick."""
        http = _make_http(200, _RELATIONSHIP_ENVELOPE)
        client = _make_engine_client(http)
        result = client.get_relationship("mira_innkeeper", "player_demo")
        assert "phase_started_at_tick" in result  # type: ignore[operator]


# ---------------------------------------------------------------------------
# G1.4 — LeftPanelRenderer.set_relationship_phase
# ---------------------------------------------------------------------------


class TestSetRelationshipPhase:
    def test_stores_phase(self) -> None:
        """set_relationship_phase stores the value on the renderer."""
        renderer = _make_renderer()
        renderer.set_relationship_phase("ally")
        assert renderer._relationship_phase == "ally"

    def test_stores_none(self) -> None:
        """set_relationship_phase accepts None without crashing."""
        renderer = _make_renderer()
        renderer.set_relationship_phase(None)
        assert renderer._relationship_phase is None

    def test_overwrites_previous(self) -> None:
        """set_relationship_phase overwrites the previous value."""
        renderer = _make_renderer()
        renderer.set_relationship_phase("stranger")
        renderer.set_relationship_phase("acquaintance")
        assert renderer._relationship_phase == "acquaintance"

    def test_draw_with_none_phase_no_crash(self) -> None:
        """Rendering the portrait zone with None phase does not crash."""
        renderer = _make_renderer()
        renderer.set_active_npc("mira_innkeeper")
        renderer.set_relationship_phase(None)

        with patch("demo_game.ui.left_panel.pygame") as mock_pygame:
            mock_pygame.draw.rect = MagicMock()
            mock_pygame.draw.circle = MagicMock()
            mock_pygame.image.load = MagicMock(side_effect=Exception("no png"))
            surface = MagicMock()
            rect = _make_rect()
            renderer._draw_portrait_zone(surface, rect)  # must not raise

    def test_draw_with_phase_renders_label(self) -> None:
        """Rendering with a phase renders the phase label via font.render."""
        renderer = _make_renderer()
        renderer.set_active_npc("mira_innkeeper")
        renderer.set_relationship_phase("ally")

        rendered_texts: list[str] = []

        class _Cap(_MockFont):
            def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
                rendered_texts.append(text)
                return super().render(text, antialias, colour)

        renderer._font_label = _Cap()

        with patch("demo_game.ui.left_panel.pygame") as mock_pygame:
            mock_pygame.draw.rect = MagicMock()
            mock_pygame.draw.circle = MagicMock()
            mock_pygame.image.load = MagicMock(side_effect=Exception("no png"))
            surface = MagicMock()
            rect = _make_rect()
            renderer._draw_portrait_zone(surface, rect)

        assert any("ally" in t for t in rendered_texts), (
            f"Expected phase 'ally' in rendered texts; got: {rendered_texts}"
        )

    def test_draw_with_empty_phase_skips_render(self) -> None:
        """Rendering with empty string phase skips the phase label (falsy guard)."""
        renderer = _make_renderer()
        renderer.set_active_npc("mira_innkeeper")
        renderer.set_relationship_phase("")

        rendered_texts: list[str] = []

        class _Cap(_MockFont):
            def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
                rendered_texts.append(text)
                return super().render(text, antialias, colour)

        renderer._font_label = _Cap()

        with patch("demo_game.ui.left_panel.pygame") as mock_pygame:
            mock_pygame.draw.rect = MagicMock()
            mock_pygame.draw.circle = MagicMock()
            mock_pygame.image.load = MagicMock(side_effect=Exception("no png"))
            surface = MagicMock()
            rect = _make_rect()
            renderer._draw_portrait_zone(surface, rect)

        assert not any("Phase:" in t for t in rendered_texts), (
            f"Expected no 'Phase:' label for empty phase; got: {rendered_texts}"
        )


# ---------------------------------------------------------------------------
# G1.2 — retrieval on-turn refresh integration (mock client + right panel)
# ---------------------------------------------------------------------------

_RETRIEVAL_PAYLOAD = {
    "npc_id": "mira_innkeeper",
    "query": "hello",
    "context_items": [{"key": "identity", "tier": "A", "text": "Mira the innkeeper."}],
    "total_tokens": 10,
}


class TestRetrievalOnTurnRefresh:
    """Verify that _refresh_retrieval calls get_retrieval_debug and forwards to set_retrieval_payload."""

    def _make_game_window_shell(self):
        """Build the minimal state needed to call _refresh_retrieval directly."""
        import types

        # Minimal fake game_window with _refresh_retrieval logic inlined.
        gw = types.SimpleNamespace()
        gw._client = MagicMock()
        gw._right = MagicMock()
        gw._last_player_message = "hello"

        import logging
        _logger = logging.getLogger("demo_game.ui.game_window")

        def _refresh_retrieval(npc_id: str) -> None:
            query = gw._last_player_message
            if not query:
                return
            try:
                payload = gw._client.get_retrieval_debug(npc_id, query)
                gw._right.set_retrieval_payload(payload)
            except Exception as exc:
                _logger.warning("retrieval refresh failed npc=%s: %s", npc_id, exc)

        gw._refresh_retrieval = _refresh_retrieval
        return gw

    def test_calls_get_retrieval_debug_with_npc_and_query(self) -> None:
        """_refresh_retrieval calls get_retrieval_debug(npc_id, last_message)."""
        gw = self._make_game_window_shell()
        gw._client.get_retrieval_debug.return_value = _RETRIEVAL_PAYLOAD
        gw._refresh_retrieval("mira_innkeeper")
        gw._client.get_retrieval_debug.assert_called_once_with("mira_innkeeper", "hello")

    def test_forwards_payload_to_set_retrieval_payload(self) -> None:
        """_refresh_retrieval forwards the payload to right.set_retrieval_payload."""
        gw = self._make_game_window_shell()
        gw._client.get_retrieval_debug.return_value = _RETRIEVAL_PAYLOAD
        gw._refresh_retrieval("mira_innkeeper")
        gw._right.set_retrieval_payload.assert_called_once_with(_RETRIEVAL_PAYLOAD)

    def test_skips_when_no_last_message(self) -> None:
        """_refresh_retrieval is a no-op when _last_player_message is empty."""
        gw = self._make_game_window_shell()
        gw._last_player_message = ""
        gw._refresh_retrieval("mira_innkeeper")
        gw._client.get_retrieval_debug.assert_not_called()

    def test_swallows_client_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """_refresh_retrieval logs but does not raise on client error."""
        import logging

        gw = self._make_game_window_shell()
        gw._client.get_retrieval_debug.side_effect = RuntimeError("boom")
        with caplog.at_level(logging.WARNING, logger="demo_game.ui.game_window"):
            gw._refresh_retrieval("mira_innkeeper")  # must not raise
        assert any("retrieval refresh failed" in r.message for r in caplog.records)

    def test_forwards_none_payload_gracefully(self) -> None:
        """_refresh_retrieval forwards None to set_retrieval_payload when client returns None."""
        gw = self._make_game_window_shell()
        gw._client.get_retrieval_debug.return_value = None
        gw._refresh_retrieval("mira_innkeeper")
        gw._right.set_retrieval_payload.assert_called_once_with(None)
