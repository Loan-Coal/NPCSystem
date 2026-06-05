"""
Module: sandbox_loop
Layer: demo_game
Purpose: Background thread that automatically advances the game clock on a
         fixed interval, enabling hands-free sandbox exploration in the demo.
Dependencies: threading, demo_game.client
Used by: demo_game.ui.game_window, demo_game.__main__
"""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient


class SandboxLoop:
    """Background thread that calls advance_clock(1) every interval_s seconds.

    Lifecycle:
        loop = SandboxLoop(client=client, interval_s=8.0)
        loop.start()   # spawns background thread
        loop.stop()    # signals thread to exit and joins it (idempotent)

    The thread is NOT a daemon thread. shutdown is cooperative via a
    threading.Event so that stop() always waits for the in-flight sleep to
    expire before returning (max wait = interval_s).

    Args:
        client: Initialised EngineClient used to call advance_clock.
        interval_s: Seconds between each advance_clock(1) call. Default 8.0.
    """

    def __init__(self, client: EngineClient, interval_s: float = 8.0) -> None:
        self._client = client
        self._interval_s = interval_s
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background auto-tick thread.

        Spawns a non-daemon thread that calls advance_clock(1) every
        interval_s seconds until stop() is called.
        """
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=False)
        self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it to exit.

        Idempotent — safe to call even if never started or already stopped.
        """
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join()

    @property
    def is_running(self) -> bool:
        """True while the background thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Thread body
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        """Thread body: wait interval_s; if not stopped, advance_clock(1)."""
        while not self._stop_event.wait(self._interval_s):
            try:
                self._client.advance_clock(1)
            except Exception as exc:
                print(f"[SandboxLoop] advance_clock error: {exc}", file=sys.stderr)
