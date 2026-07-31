"""
Regression (ISSUE-065): the WebSocket dialogue frame timeout must be at least the
HTTP dialogue timeout. The WS server fully generates the response before streaming
(dialogue_ws.py), so time-to-first-frame equals the full LLM generation (~38s cold,
measured on qwen2.5:14b; the fleet moved to the faster qwen2.5:7b in DEC-149, so the
bound remains conservative). A stale 30s WS timeout tripped before the first token
→ ws_recv_timeout.
"""

from __future__ import annotations

from demo_game.config import DemoConfig
from demo_game.constants import NPC_DIALOGUE_TIMEOUT_S as WS_DIALOGUE_TIMEOUT_S


def test_ws_dialogue_timeout_at_least_http_dialogue_timeout() -> None:
    """WS recv timeout must not be shorter than the HTTP dialogue timeout."""
    http_dialogue_timeout = DemoConfig.model_fields["NPC_DIALOGUE_TIMEOUT_S"].default
    assert WS_DIALOGUE_TIMEOUT_S >= http_dialogue_timeout
