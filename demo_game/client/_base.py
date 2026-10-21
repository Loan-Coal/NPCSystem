"""
Module: client._base
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Base EngineClient class: HTTP client lifecycle, URL helpers, and error handling.
Dependencies: httpx
Used by: demo_game.client
"""

from __future__ import annotations

import httpx


class EngineClientError(Exception):
    """Raised on any 4xx or 5xx response from the NPC Engine."""


class EngineClientBase:
    """Shared infrastructure for the NPC Engine HTTP client.

    Holds the httpx.Client, timeout configuration, URL derivation, and the
    canonical error-raise helper used by every sub-domain mixin.

    Args:
        base_url: Engine base URL, e.g. http://localhost:8000.
        api_key: Bearer token for authentication.
        dialogue_timeout: Timeout for LLM-backed calls (seconds).
        graph_timeout: Timeout for graph/clock read calls (seconds).
        _http_client: Injected httpx.Client for testing — do not use in production.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        dialogue_timeout: float = 120.0,
        graph_timeout: float = 15.0,
        *,
        _http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._dialogue_timeout = dialogue_timeout
        self._graph_timeout = graph_timeout
        self._client = _http_client or httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    @property
    def ws_url(self) -> str:
        """WebSocket base URL derived from base_url (http→ws, https→wss)."""
        return self._base_url.replace("https://", "wss://").replace("http://", "ws://")

    @property
    def api_key(self) -> str:
        """Bearer token used for authentication."""
        return self._api_key

    def _raise_for_status(self, response: httpx.Response, context: str) -> None:
        """Raise EngineClientError when the response status is 4xx or 5xx.

        Reads the canonical ErrorEnvelope shape: ``{"error": {"code": ..., "message": ...}}``.

        Args:
            response: HTTP response to inspect.
            context: Human-readable description of the call (method + path).

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        if response.status_code >= 400:
            try:
                body = response.json()
                error_block = body.get("error") or {}
                msg = error_block.get("message") or response.text[:200]
            except Exception:
                msg = response.text[:200]
            raise EngineClientError(f"{context} → HTTP {response.status_code}: {msg}")
