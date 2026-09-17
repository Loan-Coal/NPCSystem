"""
Module: test_ws_dialogue_rate_limit
Layer: tests/unit/api
Purpose: Unit tests for per-key token-bucket throughput rate limit on the
         WebSocket dialogue endpoint. Verifies that a key driving more turns
         than the configured limit is rejected with a defined close code, that
         conforming keys are unaffected, and that the limit is per key.
Does NOT: test dialogue business logic, TTS, auth rejection, or the connection cap.
Dependencies: unittest.mock
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from npc_engine.api.routes.dialogue.dialogue_ws import (
    WS_TURN_RATE_LIMIT_CLOSE_CODE,
    _active_ws_connections,
    _ws_turn_rate_buckets,
    dialogue_ws,
)
from npc_engine.config import Settings

_AUTH_A: str = "Bearer ws-rate-limit-key-A"
_AUTH_B: str = "Bearer ws-rate-limit-key-B"


def _make_ws(auth: str = _AUTH_A) -> MagicMock:
    """Return a mock WebSocket that disconnects immediately after first receive."""
    ws = MagicMock()
    ws.headers = {"Authorization": auth}
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive = AsyncMock(return_value={"type": "websocket.disconnect"})
    return ws


def _low_rate_settings() -> Settings:
    """Return Settings with burst=1 and a near-zero refill rate."""
    return Settings(
        API_KEY_SECRET="local_dev_secret_change_this_2026",
        WS_DIALOGUE_RATE_LIMIT_TURNS_PER_SECOND=0.01,
        WS_DIALOGUE_RATE_LIMIT_TURNS_BURST=1,
    )


class TestWsTurnRateLimit:
    """Per-key token-bucket throughput rate limit on the WebSocket dialogue endpoint."""

    async def test_socket_closes_when_turn_rate_exceeded(self) -> None:
        """Exceeding the per-key burst closes the socket with WS_TURN_RATE_LIMIT_CLOSE_CODE."""
        _active_ws_connections.clear()
        _ws_turn_rate_buckets.clear()

        settings = _low_rate_settings()

        with (
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws"
                ".resolve_scope_from_authorization"
            ),
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws._run_first_turn",
                new=AsyncMock(return_value="player_1"),
            ),
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws.get_proactive_queue"
            ) as mq,
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws.get_settings",
                return_value=settings,
            ),
        ):
            mq.return_value.drain.return_value = []

            # First turn: bucket is full (burst=1) — should be accepted.
            ws1 = _make_ws()
            await dialogue_ws(ws1)

            # Second turn immediately: bucket exhausted at near-zero refill — rejected.
            ws2 = _make_ws()
            await dialogue_ws(ws2)

        ws2.close.assert_called_once_with(code=WS_TURN_RATE_LIMIT_CLOSE_CODE)
        assert not ws2.accept.called, "Rate-limited turn must not be accepted."

    async def test_conforming_rate_is_unaffected(self) -> None:
        """Connections within the rate limit are accepted normally."""
        _active_ws_connections.clear()
        _ws_turn_rate_buckets.clear()

        settings = Settings(
            API_KEY_SECRET="local_dev_secret_change_this_2026",
            WS_DIALOGUE_RATE_LIMIT_TURNS_PER_SECOND=100.0,
            WS_DIALOGUE_RATE_LIMIT_TURNS_BURST=100,
        )

        with (
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws"
                ".resolve_scope_from_authorization"
            ),
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws._run_first_turn",
                new=AsyncMock(return_value="player_1"),
            ),
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws.get_proactive_queue"
            ) as mq,
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws.get_settings",
                return_value=settings,
            ),
        ):
            mq.return_value.drain.return_value = []

            for _ in range(5):
                ws = _make_ws()
                await dialogue_ws(ws)
                assert ws.accept.called, "Turn within limit must be accepted."

    async def test_limit_is_per_key_not_global(self) -> None:
        """Exhausting one key's bucket does not affect a different key's bucket."""
        _active_ws_connections.clear()
        _ws_turn_rate_buckets.clear()

        settings = _low_rate_settings()

        with (
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws"
                ".resolve_scope_from_authorization"
            ),
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws._run_first_turn",
                new=AsyncMock(return_value="player_1"),
            ),
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws.get_proactive_queue"
            ) as mq,
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws.get_settings",
                return_value=settings,
            ),
        ):
            mq.return_value.drain.return_value = []

            # Key A: first turn is within burst — accepted.
            ws_a1 = _make_ws(auth=_AUTH_A)
            await dialogue_ws(ws_a1)
            assert ws_a1.accept.called, "Key A first turn must be accepted."

            # Key A: second turn immediately — rate-limited.
            ws_a2 = _make_ws(auth=_AUTH_A)
            await dialogue_ws(ws_a2)
            ws_a2.close.assert_called_once_with(code=WS_TURN_RATE_LIMIT_CLOSE_CODE)

            # Key B: first turn has its own fresh bucket — must be accepted.
            ws_b = _make_ws(auth=_AUTH_B)
            await dialogue_ws(ws_b)
            assert ws_b.accept.called, "Key B first turn must be accepted (independent bucket)."
