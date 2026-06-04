"""
Module: world_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls GET /v1/system/engines and
         GET /v1/system/events on a fixed interval, exposing the latest
         snapshots thread-safely for the WORLD panel to render.
         Mirrors the WorldStatePoller pattern.
Dependencies: threading, sys, demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

_logger = logging.getLogger(__name__)
_DEFAULT_INTERVAL_S = 5.0
_DEFAULT_EVENT_LIMIT = 20


class WorldPoller:
    """Background daemon thread that polls engine-status and recent-events endpoints.

    Polls every ``interval_s`` seconds. Results are stored under a lock so the
    render loop can read them without blocking or racing.

    Exceptions during polling are swallowed and printed to stderr so a transient
    network error never crashes the render loop.

    Args:
        client: Initialised EngineClient.
        interval_s: Poll interval in seconds. Defaults to 5.0.
        event_limit: Number of recent events to fetch per poll. Defaults to 20.
    """

    def __init__(
        self,
        client: EngineClient,
        interval_s: float = _DEFAULT_INTERVAL_S,
        event_limit: int = _DEFAULT_EVENT_LIMIT,
    ) -> None:
        self._client = client
        self._interval = interval_s
        self._event_limit = event_limit

        self._lock = threading.Lock()
        self._engines: list[dict] = []
        self._events: list[dict] = []

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background polling daemon thread. Safe to call once."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def get_engines(self) -> list[dict]:
        """Return the latest engine-status snapshot.

        Thread-safe. Returns a copy so callers cannot mutate internal state.

        Returns:
            List of engine status dicts. Empty until the first successful poll.
        """
        with self._lock:
            return list(self._engines)

    def get_events(self) -> list[dict]:
        """Return the latest recent-events snapshot.

        Thread-safe. Returns a copy so callers cannot mutate internal state.

        Returns:
            List of event dicts ordered by tick descending. Empty until first poll.
        """
        with self._lock:
            return list(self._events)

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: immediate first fetch, then interval-based."""
        self._poll_once()
        while not self._stop_event.wait(self._interval):
            self._poll_once()

    def _poll_once(self) -> None:
        """Fetch both endpoints and update shared state under lock.

        Silently swallows all exceptions — a poll failure should never crash
        the render loop.
        """
        try:
            engines = self._client.get_engine_status()
        except Exception as exc:
            _logger.warning("engine_status error: %s", exc)
            engines = None

        try:
            events = self._client.get_recent_events(limit=self._event_limit)
        except Exception as exc:
            _logger.warning("recent_events error: %s", exc)
            events = None

        with self._lock:
            if engines is not None:
                self._engines = engines
            if events is not None:
                self._events = events
