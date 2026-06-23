"""
Module: director_beat_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls GET /v1/dialogue/director-beats
         on a fixed interval and exposes the latest list thread-safely.
         Fires a NEW-beat flag when the head beat changes so the HUD cue
         renderer can display a transient "something stirs…" message.
Dependencies: threading, demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

_DEFAULT_INTERVAL_S = 4.0
_DEFAULT_LIMIT = 10

_logger = logging.getLogger(__name__)


class DirectorBeatPoller:
    """Background daemon that polls director beats and detects new arrivals.

    Polls ``client.get_director_beats(limit)`` every ``interval_s`` seconds.
    A beat is considered *new* when the first element in the returned list
    differs from the previously seen first element (compared by ``tick`` +
    ``beat_kind`` identity).

    Call ``pop_new_beat()`` each render frame to consume and reset the flag.

    Args:
        client: Initialised EngineClient.
        interval_s: Poll interval in seconds.
        limit: Maximum number of beats to fetch.
    """

    def __init__(
        self,
        client: EngineClient,
        interval_s: float = _DEFAULT_INTERVAL_S,
        limit: int = _DEFAULT_LIMIT,
    ) -> None:
        self._client = client
        self._interval = interval_s
        self._limit = limit

        self._lock = threading.Lock()
        self._beats: list[dict] = []
        self._last_head_key: str | None = None
        self._new_beat: dict | None = None  # pending cue to display

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background polling daemon thread. Safe to call once."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def get_beats(self) -> list[dict]:
        """Return the latest director-beats snapshot.

        Thread-safe. Returns a copy so callers cannot mutate internal state.
        """
        with self._lock:
            return list(self._beats)

    def pop_new_beat(self) -> dict | None:
        """Consume and return the pending new-beat cue, if any.

        Call once per render frame. Returns the beat dict if a new beat
        arrived since the last call, otherwise None.

        Returns:
            Beat dict (with beat_kind, reason, npc_id, player_id, tick),
            or None when nothing new.
        """
        with self._lock:
            beat = self._new_beat
            self._new_beat = None
            return beat

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: wait up to interval_s then poll."""
        while not self._stop.is_set():
            self._stop.wait(self._interval)
            if self._stop.is_set():
                break
            self._poll_once()

    def _poll_once(self) -> None:
        """Fetch beats, update state, and set new-beat flag if head changed."""
        try:
            beats = self._client.get_director_beats(self._limit)
        except Exception as exc:
            _logger.warning("director_beat poll error: %s", exc)
            return

        with self._lock:
            self._beats = beats
            if beats:
                head = beats[0]
                key = f"{head.get('tick')}:{head.get('beat_kind')}"
                if key != self._last_head_key:
                    self._last_head_key = key
                    self._new_beat = head
