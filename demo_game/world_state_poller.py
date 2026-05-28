"""
Module: world_state_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls GET /v1/graph/nodes/world_state on a fixed
         interval and exposes the current epoch and active_conditions thread-safely.
         Mirrors the GraphPoller pattern so GameWindow can read live world state without
         blocking the render loop.
Dependencies: threading, sys, demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient


class WorldStatePoller:
    """Background daemon thread that periodically polls the engine world state.

    Polls `GET /v1/graph/nodes/world_state` every `interval_s` seconds. The
    latest epoch and active_conditions are stored thread-safely and returned
    on each call to `get_state()`.

    Exceptions during polling are swallowed and printed to stderr so a transient
    network error never crashes the render loop.

    Args:
        client: Initialised EngineClient.
        interval_s: Poll interval in seconds. Defaults to 2.0.
    """

    def __init__(self, client: EngineClient, interval_s: float = 2.0) -> None:
        self._client = client
        self._interval = interval_s

        self._lock = threading.Lock()
        self._epoch: str = ""
        self._conditions: list[str] = []

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background polling daemon thread. Safe to call once."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def get_state(self) -> tuple[str, list[str]]:
        """Return the latest (epoch, active_conditions) snapshot.

        Thread-safe. Returns copies so callers cannot mutate internal state.

        Returns:
            Tuple of (epoch_str, active_conditions_list). Both are empty until
            the first successful poll completes.
        """
        with self._lock:
            return self._epoch, list(self._conditions)

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: immediate first fetch, then interval-based."""
        self._poll_once()
        while not self._stop_event.wait(self._interval):
            self._poll_once()

    def _poll_once(self) -> None:
        """Fetch world state and update shared epoch/conditions under lock.

        Silently swallows all exceptions — a poll failure should never crash
        the render loop.
        """
        try:
            ws = self._client.get_world_state()
            if ws is None:
                return
            epoch = ws.get("epoch", "")
            conditions = list(ws.get("active_conditions", []))
            with self._lock:
                self._epoch = epoch
                self._conditions = conditions
        except Exception as exc:
            print(f"[WorldStatePoller] error: {exc}", file=sys.stderr)
