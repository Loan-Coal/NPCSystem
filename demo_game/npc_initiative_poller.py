"""
Module: npc_initiative_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls GET /v1/dialogue/pending for pending
         NPC-initiated intents, exposing batches to the main thread via pop_pending().
         Follows the NpcNeedsPoller pattern; player_id is fixed at construction.
Dependencies: threading, demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from demo_game.intent_ui import INTENT_POLL_INTERVAL_SECONDS

if TYPE_CHECKING:
    from demo_game.client import EngineClient

_logger = logging.getLogger(__name__)


class NpcInitiativePoller:
    """Background daemon that polls pending NPC-initiated intents for a player.

    Calls ``client.get_pending_intents(player_id)`` every ``interval_s`` seconds.
    New batches accumulate in an internal list; call ``pop_pending()`` from the
    main thread to drain it atomically.

    The endpoint is destructive — each call marks returned intents as delivered.
    Never call ``client.get_pending_intents`` from multiple threads.

    Args:
        client: Initialised EngineClient.
        player_id: Fixed player character ID to poll intents for.
        interval_s: Poll interval in seconds.
    """

    def __init__(
        self,
        client: EngineClient,
        player_id: str,
        interval_s: float = INTENT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._client = client
        self._player_id = player_id
        self._interval = interval_s

        self._lock = threading.Lock()
        self._pending: list[dict] = []

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background polling daemon thread. Safe to call once."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pop_pending(self) -> list[dict]:
        """Drain and return all intents accumulated since the last call.

        Thread-safe. Returns a new list; the internal buffer is cleared.

        Returns:
            List of pending intent dicts (may be empty). Ordered by score DESC
            as returned by the server.
        """
        with self._lock:
            batch = list(self._pending)
            self._pending = []
        return batch

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: sleep interval_s, then poll."""
        while not self._stop.is_set():
            self._stop.wait(self._interval)
            if not self._stop.is_set():
                self._poll_once()

    def _poll_once(self) -> None:
        """Fetch pending intents and append to the internal buffer under lock.

        Silently swallows all exceptions to avoid crashing the render loop.
        """
        try:
            intents = self._client.get_pending_intents(self._player_id)
            if intents:
                with self._lock:
                    self._pending.extend(intents)
        except Exception as exc:
            _logger.warning("initiative poll error: %s", exc)
