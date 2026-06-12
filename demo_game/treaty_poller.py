"""
Module: treaty_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls faction treaties for all demo
         factions on a fixed interval, de-duplicating by treaty id and
         exposing the merged list thread-safely for the TREATY panel.
Dependencies: threading, demo_game.client, demo_game.constants
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from demo_game.constants import DEMO_FACTIONS

if TYPE_CHECKING:
    from demo_game.client import EngineClient

_logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL_S: float = 8.0


class TreatyPoller:
    """Background daemon that polls active treaties for all demo factions.

    Queries ``client.get_faction_treaties`` for each faction in
    ``DEMO_FACTIONS`` and merges the results, de-duplicating by treaty id.
    The merged list is exposed via ``get_treaties()`` for the TREATY panel.

    Exceptions during polling are swallowed and logged as WARNING so a
    transient network error never crashes the render loop.

    Args:
        client: Initialised EngineClient.
        interval_s: Poll interval in seconds. Defaults to 8.0.
    """

    def __init__(
        self,
        client: EngineClient,
        interval_s: float = _DEFAULT_INTERVAL_S,
    ) -> None:
        self._client = client
        self._interval = interval_s

        self._lock = threading.Lock()
        self._treaties: list[dict] = []

        self._stop = threading.Event()
        self._immediate = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background polling daemon thread. Safe to call once."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def get_treaties(self) -> list[dict]:
        """Return the latest merged treaty list.

        Thread-safe. Returns a copy so callers cannot mutate internal state.

        Returns:
            De-duplicated list of treaty dicts across all demo factions.
            Empty until the first successful poll.
        """
        with self._lock:
            return list(self._treaties)

    def refresh(self) -> None:
        """Trigger an immediate out-of-band poll (e.g. after broker/break)."""
        self._immediate.set()

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: immediate first fetch, then interval-based."""
        self._poll_once()
        while not self._stop.is_set():
            self._immediate.wait(self._interval)
            self._immediate.clear()
            self._poll_once()

    def _poll_once(self) -> None:
        """Fetch treaties from all demo factions and merge under lock.

        Silently swallows all exceptions. Individual faction failures fall back
        to an empty list for that faction so partial data is still shown.
        """
        seen: set[str] = set()
        merged: list[dict] = []
        for faction_id in DEMO_FACTIONS:
            try:
                treaties = self._client.get_faction_treaties(faction_id)
                for t in treaties:
                    tid = str(t.get("id") or t.get("treaty_id") or "")
                    if tid and tid not in seen:
                        seen.add(tid)
                        merged.append(t)
                    elif not tid:
                        merged.append(t)
            except Exception as exc:
                _logger.warning("treaty poll error faction=%s: %s", faction_id, exc)
        with self._lock:
            self._treaties = merged
