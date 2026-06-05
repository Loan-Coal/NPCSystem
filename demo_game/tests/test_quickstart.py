"""
Module: test_quickstart
Layer: demo_game (tests)
Purpose: TDD unit tests for quickstart.py — verifies all HTTP calls and output.
Dependencies: demo_game.quickstart, unittest.mock (no network, no engine required)
Used by: make test-demo
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status_code: int, body: dict) -> MagicMock:
    """Build a mock httpx.Response with the given status and JSON body."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = str(body)
    return resp


def _make_mock_client(npc_reply: str = "The market stirs with strange rumours today.") -> MagicMock:
    """Build a mock httpx.Client that satisfies all quickstart calls."""
    client = MagicMock()

    # GET /health → 200
    health_resp = _make_response(200, {"status": "ok"})

    # POST /v1/graph/nodes/Location → 200 (idempotency: 409 also acceptable)
    node_resp = _make_response(200, {"data": {"id": "quickstart_market"}})

    # POST /v1/graph/nodes/Character → 200
    char_resp = _make_response(200, {"data": {"id": "quickstart_trader"}})

    # GET /v1/graph/nodes/Event/quickstart_rumor → 404 (not exists)
    event_404 = _make_response(404, {})

    # POST /v1/graph/nodes/Event → 200
    event_resp = _make_response(200, {"data": {"id": "quickstart_rumor"}})

    # POST /v1/graph/edges/LOCATED_AT → 200
    located_at_resp = _make_response(200, {"data": {}})

    # GET /v1/graph/edges/KNOWS_ABOUT/quickstart_trader/quickstart_rumor → 404
    ka_404 = _make_response(404, {})

    # POST /v1/graph/edges/KNOWS_ABOUT → 200
    knows_about_resp = _make_response(200, {"data": {}})

    # POST /v1/dialogue → 200
    dialogue_resp = _make_response(200, {
        "npc_id": "quickstart_trader",
        "response_text": npc_reply,
        "emotion": "neutral",
    })

    def request_side_effect(method: str, url: str, **kwargs):
        """Route mock responses based on method + URL."""
        if method == "GET" and url == "/health":
            return health_resp
        if method == "GET" and "/v1/graph/nodes/Event/" in url:
            return event_404
        if method == "GET" and "/v1/graph/edges/KNOWS_ABOUT/" in url:
            return ka_404
        if method == "GET" and "/v1/graph/nodes/Location/" in url:
            return event_404  # treat as 404 so seed runs
        if method == "GET" and "/v1/graph/nodes/Character/" in url:
            return event_404  # treat as 404 so seed runs
        if method == "POST" and "/v1/graph/nodes/Location" in url:
            return node_resp
        if method == "POST" and "/v1/graph/nodes/Character" in url:
            return char_resp
        if method == "POST" and "/v1/graph/nodes/Event" in url:
            return event_resp
        if method == "POST" and "/v1/graph/edges/LOCATED_AT" in url:
            return located_at_resp
        if method == "POST" and "/v1/graph/edges/KNOWS_ABOUT" in url:
            return knows_about_resp
        if method == "POST" and url == "/v1/dialogue":
            return dialogue_resp
        # Default fallback
        return _make_response(200, {})

    client.request.side_effect = request_side_effect
    # Also wire .get / .post shorthand in case quickstart uses those
    def get_side(url, **kw):
        return request_side_effect("GET", url, **kw)
    def post_side(url, **kw):
        return request_side_effect("POST", url, **kw)
    client.get.side_effect = get_side
    client.post.side_effect = post_side
    return client


def _run_main_with_mock(mock_client: MagicMock, env: dict | None = None) -> str:
    """Import quickstart and call main() with httpx.Client patched.

    Args:
        mock_client: Mock httpx.Client instance to inject.
        env: Optional env-var overrides (defaults to NPC_API_KEY=test-key).

    Returns:
        Captured stdout text.
    """
    import io
    import demo_game.quickstart as qs  # noqa: PLC0415

    env_overrides = env or {"NPC_API_KEY": "test-key"}
    stdout_buf = io.StringIO()

    with (
        patch("demo_game.quickstart.httpx.Client", return_value=mock_client),
        patch.dict("os.environ", env_overrides),
        patch("sys.stdout", stdout_buf),
    ):
        qs.main()

    return stdout_buf.getvalue()


# ---------------------------------------------------------------------------
# Tests: HTTP call coverage
# ---------------------------------------------------------------------------


def test_quickstart_checks_health() -> None:
    """quickstart.main() issues a GET /health call."""
    mock_client = _make_mock_client()
    _run_main_with_mock(mock_client)

    get_urls = [c.args[0] for c in mock_client.get.call_args_list]
    assert "/health" in get_urls, f"GET /health not called; got: {get_urls}"


def test_quickstart_seeds_location() -> None:
    """quickstart.main() issues a POST /v1/graph/nodes/Location call."""
    mock_client = _make_mock_client()
    _run_main_with_mock(mock_client)

    post_urls = [c.args[0] for c in mock_client.post.call_args_list]
    assert any("/v1/graph/nodes/Location" in u for u in post_urls), (
        f"POST /v1/graph/nodes/Location not called; got: {post_urls}"
    )


def test_quickstart_seeds_character() -> None:
    """quickstart.main() issues a POST /v1/graph/nodes/Character call."""
    mock_client = _make_mock_client()
    _run_main_with_mock(mock_client)

    post_urls = [c.args[0] for c in mock_client.post.call_args_list]
    assert any("/v1/graph/nodes/Character" in u for u in post_urls), (
        f"POST /v1/graph/nodes/Character not called; got: {post_urls}"
    )


def test_quickstart_seeds_knows_about_edge() -> None:
    """quickstart.main() issues a POST /v1/graph/edges/KNOWS_ABOUT call."""
    mock_client = _make_mock_client()
    _run_main_with_mock(mock_client)

    post_urls = [c.args[0] for c in mock_client.post.call_args_list]
    assert any("/v1/graph/edges/KNOWS_ABOUT" in u for u in post_urls), (
        f"POST /v1/graph/edges/KNOWS_ABOUT not called; got: {post_urls}"
    )


def test_quickstart_posts_dialogue() -> None:
    """quickstart.main() issues a POST /v1/dialogue call."""
    mock_client = _make_mock_client()
    _run_main_with_mock(mock_client)

    post_urls = [c.args[0] for c in mock_client.post.call_args_list]
    assert "/v1/dialogue" in post_urls, (
        f"POST /v1/dialogue not called; got: {post_urls}"
    )


def test_quickstart_prints_npc_reply() -> None:
    """quickstart.main() prints the NPC response_text to stdout."""
    npc_reply = "The market stirs with strange rumours today."
    mock_client = _make_mock_client(npc_reply=npc_reply)
    output = _run_main_with_mock(mock_client)

    assert npc_reply in output, f"NPC reply not printed; stdout was: {output!r}"


def test_quickstart_dialogue_body_shape() -> None:
    """quickstart.main() sends the expected dialogue body fields."""
    mock_client = _make_mock_client()
    _run_main_with_mock(mock_client)

    dialogue_calls = [
        c for c in mock_client.post.call_args_list
        if c.args[0] == "/v1/dialogue"
    ]
    assert dialogue_calls, "POST /v1/dialogue was not called"
    body = dialogue_calls[0].kwargs.get("json", {})
    assert body.get("player_id") == "player_demo"
    assert body.get("npc_id") == "quickstart_trader"
    assert body.get("location_id") == "quickstart_market"
    assert "player_message" in body
