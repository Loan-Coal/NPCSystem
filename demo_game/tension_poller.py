"""
Module: tension_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls GET /v1/graph/nodes/world_state to
         extract max_event_severity and quest_generation_rate, exposing them
         thread-safely for the story-pacing tension HUD (H3.5).
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

_DEFAULT_INTERVAL_S: float = 4.0

_DEFAULT_MAX_SEVERITY: int = 0
_DEFAULT_QUEST_RATE: float = 0.0


class TensionPoller:
    """Background daemon that polls world-state pacing metrics for the HUD.

    Extracts ``max_event_severity`` and ``quest_generation_rate`` from the
    WorldState node. Both metrics feed the story-pacing tension HUD (H3.5).

    Exceptions during polling are swallowed and logged as WARNING so a transient
    network error never crashes the render loop.

    Args:
        client: Initialised EngineClient.
        interval_s: Poll interval in seconds. Defaults to 4.0.
    """

    def __init__(
        self,
        client: EngineClient,
        interval_s: float = _DEFAULT_INTERVAL_S,
    ) -> None:
        self._client = client
        self._interval = interval_s

        self._lock = threading.Lock()
        self._max_severity: int = _DEFAULT_MAX_SEVERITY
        self._quest_rate: float = _DEFAULT_QUEST_RATE

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background polling daemon thread. Safe to call once."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def get_tension(self) -> tuple[int, float]:
        """Return (max_event_severity, quest_generation_rate) snapshot.

        Thread-safe. Returns defaults (0, 0.0) until the first successful poll.

        Returns:
            Tuple of (max_event_severity_int, quest_generation_rate_float).
        """
        with self._lock:
            return self._max_severity, self._quest_rate

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: immediate first fetch, then interval-based."""
        self._poll_once()
        while not self._stop.wait(self._interval):
            self._poll_once()

    def _poll_once(self) -> None:
        """Fetch world state and update tension metrics under lock.

        Silently swallows all exceptions — a poll failure should never crash
        the render loop.
        """
        try:
            ws = self._client.get_world_state()
            if ws is None:
                return
            severity = int(ws.get("max_event_severity", _DEFAULT_MAX_SEVERITY))
            rate = float(ws.get("quest_generation_rate", _DEFAULT_QUEST_RATE))
            with self._lock:
                self._max_severity = severity
                self._quest_rate = rate
        except Exception as exc:
            _logger.warning("tension poll error: %s", exc)
