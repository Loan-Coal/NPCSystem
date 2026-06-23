"""
Module: pledge_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls GET /v1/admin/pledges/characters/{npc_id}
         for the active NPC on a fixed interval, exposing the latest pledge list
         thread-safely. Mirrors the NpcPoliticsPoller pattern.
Dependencies: threading, demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

_logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL_S: float = 5.0


class PledgePoller:
    """Background daemon that polls active pledges for the current NPC.

    Calls ``client.get_pledges_for_npc`` every ``interval_s`` seconds.
    Results are stored under a lock and read via ``get_pledges()``.

    Calling ``set_active_npc()`` clears cached pledges and triggers an
    immediate re-poll so the OATH panel updates instantly on NPC switch.

    Exceptions during polling are swallowed and logged as WARNING so a
    transient network error never crashes the render loop.

    Args:
        client: Initialised EngineClient.
        interval_s: Poll interval in seconds. Defaults to 5.0.
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
        self._pledges: list[dict] = []

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
        """Switch the target NPC, clear cached pledges, trigger immediate poll.

        Args:
            npc_id: New active NPC ID, or None to stop polling.
        """
        with self._lock:
            self._npc_id = npc_id
            self._pledges = []
        self._immediate.set()

    def get_pledges(self) -> list[dict]:
        """Return the latest pledges snapshot for the active NPC.

        Thread-safe. Returns a copy so callers cannot mutate internal state.

        Returns:
            List of pledge dicts. Empty until the first successful poll.
        """
        with self._lock:
            return list(self._pledges)

    def refresh(self) -> None:
        """Trigger an immediate out-of-band poll (e.g. after swear/break)."""
        self._immediate.set()

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
        """Fetch pledges for the active NPC and update shared state under lock.

        Silently swallows all exceptions. Discards results if the NPC
        switched mid-request.
        """
        with self._lock:
            npc_id = self._npc_id
        if npc_id is None:
            return
        try:
            pledges = self._client.get_pledges_for_npc(npc_id)
            with self._lock:
                if self._npc_id == npc_id:
                    self._pledges = pledges
        except Exception as exc:
            _logger.warning("pledge poll error npc=%s: %s", npc_id, exc)
