"""
Module: npc_needs_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls Need nodes for the active NPC on a
         fixed interval, exposing the latest snapshot thread-safely.
         Mirrors the EmotionPoller pattern; switches instantly when the active NPC
         changes via set_active_npc().
Dependencies: threading, sys, demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

_DEFAULT_INTERVAL_S = 5.0


_logger = logging.getLogger(__name__)
class NpcNeedsPoller:
    """Background daemon that polls Need nodes for the currently active NPC.

    Calls ``client.get_needs_for_npc(npc_id)`` every ``interval_s`` seconds.
    Results are stored under a lock; read them with ``get_needs()``.

    Calling ``set_active_npc()`` clears cached data and triggers an immediate
    re-poll so the NEEDS panel updates instantly on NPC switch.

    Exceptions during polling are swallowed and printed to stderr so a transient
    network error never crashes the render loop.

    Args:
        client: Initialised EngineClient.
        interval_s: Poll interval in seconds. Defaults to 5.0.
    """

    def __init__(self, client: EngineClient, interval_s: float = _DEFAULT_INTERVAL_S) -> None:
        self._client = client
        self._interval = interval_s

        self._lock = threading.Lock()
        self._npc_id: str | None = None
        self._needs: list[dict] = []

        self._immediate = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background polling daemon thread. Safe to call once."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_active_npc(self, npc_id: str | None) -> None:
        """Switch the target NPC, clear cached needs, and trigger an immediate poll.

        Args:
            npc_id: New active NPC ID, or None to stop polling.
        """
        with self._lock:
            self._npc_id = npc_id
            self._needs = []
        self._immediate.set()

    def get_needs(self) -> list[dict]:
        """Return the latest needs snapshot for the active NPC.

        Thread-safe. Returns a copy so callers cannot mutate internal state.

        Returns:
            List of Need node dicts. Empty until the first successful poll.
        """
        with self._lock:
            return list(self._needs)

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: wait up to interval_s or until signalled, then poll."""
        while not self._stop.is_set():
            self._immediate.wait(self._interval)
            self._immediate.clear()
            self._poll_once()

    def _poll_once(self) -> None:
        """Fetch needs for the active NPC and update shared state under lock.

        Silently swallows all exceptions. Discards the result if the NPC
        switched mid-request.
        """
        with self._lock:
            npc_id = self._npc_id
        if npc_id is None:
            return
        try:
            needs = self._client.get_needs_for_npc(npc_id)
            with self._lock:
                if self._npc_id == npc_id:
                    self._needs = needs
        except Exception as exc:
            _logger.warning("error: %s", exc)
