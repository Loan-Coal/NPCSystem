"""
Module: npc_schemes_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls the schemes endpoint for the active
         NPC on a fixed interval, exposing the latest scheme list thread-safely.
         Feeds the G2.2 intrigue board. Mirrors NpcPlayerModelPoller.
Dependencies: threading, demo_game.client
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


class NpcSchemesPoller:
    """Background daemon that polls the scheme board for the active NPC.

    Calls ``client.get_schemes(npc_id)`` every ``interval_s`` seconds. Results
    are stored under a lock; read them with ``get_schemes()``.

    Calling ``set_active_npc()`` clears cached data and triggers an immediate
    re-poll so the INTRIGUE panel updates instantly on NPC switch.

    Exceptions during polling are swallowed so a transient network error never
    crashes the render loop.

    Args:
        client: Initialised EngineClient.
        interval_s: Poll interval in seconds.
    """

    def __init__(
        self,
        client: EngineClient,
        interval_s: float = _DEFAULT_INTERVAL_S,
    ) -> None:
        self._client = client
        self._interval = interval_s

        self._lock = threading.Lock()
        self._npc_id: str | None = None
        self._schemes: list[dict] = []

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
        """Switch the target NPC, clear cached schemes, and trigger immediate poll.

        Args:
            npc_id: New active NPC ID, or None to stop polling.
        """
        with self._lock:
            self._npc_id = npc_id
            self._schemes = []
        self._immediate.set()

    def get_schemes(self) -> list[dict]:
        """Return the latest scheme list for the active NPC (thread-safe copy).

        Returns:
            List of scheme dicts (may be empty when not yet fetched or none exist).
        """
        with self._lock:
            return list(self._schemes)

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: wait up to interval_s or until signalled."""
        while not self._stop.is_set():
            self._immediate.wait(self._interval)
            self._immediate.clear()
            self._poll_once()

    def _poll_once(self) -> None:
        """Fetch schemes for the active NPC and update shared state.

        Silently swallows all exceptions. Discards the result if the NPC switched
        mid-request.
        """
        with self._lock:
            npc_id = self._npc_id
        if npc_id is None:
            return
        try:
            schemes = self._client.get_schemes(npc_id)
            with self._lock:
                if self._npc_id == npc_id:
                    self._schemes = schemes
        except Exception as exc:
            _logger.warning("schemes poll error npc=%s: %s", npc_id, exc)
