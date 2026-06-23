"""
Module: npc_player_model_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls the player-model endpoint for
         the active NPC on a fixed interval, exposing the latest snapshot
         thread-safely. Mirrors NpcGoalsPoller.
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


class NpcPlayerModelPoller:
    """Background daemon that polls the player-model for the active NPC.

    Calls ``client.get_player_model(npc_id, player_id)`` every
    ``interval_s`` seconds.  Results are stored under a lock; read them
    with ``get_model()``.

    Calling ``set_active_npc()`` clears cached data and triggers an
    immediate re-poll so the PLAYER MODEL panel updates instantly on NPC
    switch.

    Exceptions during polling are swallowed so a transient network error
    never crashes the render loop.

    Args:
        client: Initialised EngineClient.
        player_id: Fixed player identifier (e.g. ``player_demo``).
        interval_s: Poll interval in seconds.
    """

    def __init__(
        self,
        client: EngineClient,
        player_id: str,
        interval_s: float = _DEFAULT_INTERVAL_S,
    ) -> None:
        self._client = client
        self._player_id = player_id
        self._interval = interval_s

        self._lock = threading.Lock()
        self._npc_id: str | None = None
        self._model: dict | None = None

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
        """Switch the target NPC, clear cached model, and trigger immediate poll.

        Args:
            npc_id: New active NPC ID, or None to stop polling.
        """
        with self._lock:
            self._npc_id = npc_id
            self._model = None
        self._immediate.set()

    def get_model(self) -> dict | None:
        """Return the latest player-model snapshot for the active NPC.

        Thread-safe. Returns a copy so callers cannot mutate internal state.

        Returns:
            Player-model dict, or None when not yet fetched or NPC has no
            model (404 response from engine).
        """
        with self._lock:
            return dict(self._model) if self._model is not None else None

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
        """Fetch player model for the active NPC and update shared state.

        Silently swallows all exceptions. Discards the result if the NPC
        switched mid-request.
        """
        with self._lock:
            npc_id = self._npc_id
        if npc_id is None:
            return
        try:
            model = self._client.get_player_model(npc_id, self._player_id)
            with self._lock:
                if self._npc_id == npc_id:
                    self._model = model
        except Exception as exc:
            _logger.warning("player_model poll error npc=%s: %s", npc_id, exc)
