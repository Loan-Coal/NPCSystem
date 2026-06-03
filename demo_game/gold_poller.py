"""
Module: gold_poller
Layer: demo_game
Purpose: Background thread that polls the player character's currency_balance every interval_s seconds.
Dependencies: demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import sys
import threading
import time

from demo_game.client import EngineClient

_CHAR_NODE_TYPE = "Character"


class GoldPoller:
    """Polls the player's currency_balance on a background daemon thread.

    Thread-safe: get_gold() may be called from the main thread at any time.

    Args:
        client: Authenticated EngineClient.
        player_id: Character node ID of the player.
        interval_s: Polling interval in seconds (default 3.0).
    """

    def __init__(
        self,
        client: EngineClient,
        player_id: str,
        interval_s: float = 3.0,
    ) -> None:
        self._client = client
        self._player_id = player_id
        self._interval_s = interval_s
        self._gold: int | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the background polling daemon thread."""
        threading.Thread(target=self._run, daemon=True).start()

    def get_gold(self) -> int | None:
        """Return the most recently polled gold balance.

        Returns:
            Currency balance as an integer, or None if no poll has completed yet.
        """
        with self._lock:
            return self._gold

    def _run(self) -> None:
        """Poll loop — runs until the process exits (daemon thread)."""
        while True:
            try:
                char = self._client.get_node(_CHAR_NODE_TYPE, self._player_id)
                gold = int((char or {}).get("currency_balance") or 0)
                with self._lock:
                    self._gold = gold
            except Exception as exc:
                print(f"[gold_poller] poll failed: {exc}", file=sys.stderr)
            time.sleep(self._interval_s)
