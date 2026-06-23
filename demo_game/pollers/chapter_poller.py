"""
Module: chapter_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls GET /v1/chapters/current on a fixed
         interval and exposes the current chapter/act snapshot thread-safely.
         Falls back to a quest-count banner if no chapter data is available.
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

_DEFAULT_INTERVAL_S: float = 10.0


class ChapterPoller:
    """Background daemon that polls the current chapter/act from the engine.

    Calls ``client.get_current_chapter()`` every ``interval_s`` seconds.
    The latest snapshot is stored under a lock and read via ``get_chapter()``.

    When no chapter data is available (engine returns None), the snapshot
    remains None — the banner consumer should fall back to a quest-count display.

    Exceptions during polling are swallowed and logged as WARNING so a transient
    network error never crashes the render loop.

    Args:
        client: Initialised EngineClient.
        interval_s: Poll interval in seconds. Defaults to 10.0.
    """

    def __init__(
        self,
        client: EngineClient,
        interval_s: float = _DEFAULT_INTERVAL_S,
    ) -> None:
        self._client = client
        self._interval = interval_s

        self._lock = threading.Lock()
        self._chapter: dict | None = None

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background polling daemon thread. Safe to call once."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def get_chapter(self) -> dict | None:
        """Return the latest chapter snapshot.

        Thread-safe. Returns None until the first successful poll or if no
        chapter is currently open.

        Returns:
            Chapter dict with id, name, started_at_tick, theme, status keys,
            or None when no chapter is open.
        """
        with self._lock:
            return self._chapter

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: immediate first fetch, then interval-based."""
        self._poll_once()
        while not self._stop.wait(self._interval):
            self._poll_once()

    def _poll_once(self) -> None:
        """Fetch current chapter and update shared state under lock.

        Silently swallows all exceptions — a poll failure should never crash
        the render loop.
        """
        try:
            chapter = self._client.get_current_chapter()
            with self._lock:
                self._chapter = chapter
        except Exception as exc:
            _logger.warning("chapter poll error: %s", exc)
