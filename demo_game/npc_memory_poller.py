"""
Module: npc_memory_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls Memory nodes for the active NPC on a
         fixed interval, exposing the latest snapshot thread-safely.
         Mirrors the NpcGoalsPoller pattern; switches instantly when the active NPC
         changes via set_active_npc().
Dependencies: threading, sys, demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

_DEFAULT_INTERVAL_S = 5.0


class NpcMemoryPoller:
    """Background daemon that polls Memory nodes for the currently active NPC.

    Calls ``client.get_memories(npc_id)`` every ``interval_s`` seconds.
    Results are stored under a lock; read them with ``get_memories()``.

    Calling ``set_active_npc()`` clears cached data and triggers an immediate
    re-poll so the MEMORY panel updates instantly on NPC switch.

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
        self._memories: list[dict] = []

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
        """Switch the target NPC, clear cached memories, and trigger an immediate poll.

        Args:
            npc_id: New active NPC ID, or None to stop polling.
        """
        with self._lock:
            self._npc_id = npc_id
            self._memories = []
        self._immediate.set()

    def get_memories(self) -> list[dict]:
        """Return the latest memories snapshot for the active NPC.

        Thread-safe. Returns a copy so callers cannot mutate internal state.

        Returns:
            List of Memory node dicts. Empty until the first successful poll.
        """
        with self._lock:
            return list(self._memories)

    def refresh(self) -> None:
        """Trigger an immediate re-poll (e.g., after a consolidate action)."""
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
        """Fetch memories for the active NPC and update shared state under lock.

        Silently swallows all exceptions. Discards the result if the NPC
        switched mid-request.
        """
        with self._lock:
            npc_id = self._npc_id
        if npc_id is None:
            return
        try:
            memories = self._client.get_memories(npc_id)
            with self._lock:
                if self._npc_id == npc_id:
                    self._memories = memories
        except Exception as exc:
            print(f"[NpcMemoryPoller] error: {exc}", file=sys.stderr)
