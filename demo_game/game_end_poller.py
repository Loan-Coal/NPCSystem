"""
Module: game_end_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that periodically evaluates the S7.1 win/lose
         conditions by polling player reputation and iron_legion CONTROLS edges.
         Exposes the latest ObjectiveState thread-safely for the render loop.
Dependencies: threading, sys, demo_game.client, demo_game.game_end_checker
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING

from demo_game.game_end_checker import (
    LOSE_FACTION_ID,
    ObjectiveState,
    detect_first_allied_faction,
    evaluate_game_end,
)

if TYPE_CHECKING:
    from demo_game.client import EngineClient

_INITIAL_STATE = ObjectiveState(
    faction_standings={},
    iron_legion_controls=[],
    outcome=None,
)


class GameEndPoller:
    """Background daemon that polls win/lose conditions every interval_s seconds.

    Calls `GET /v1/graph/characters/{player_id}/reputation` for faction standings
    and `GET /v1/graph/edges/CONTROLS?src_id=iron_legion` for the lose condition.
    Stores the result in an ObjectiveState; raises no exceptions to the caller —
    transient errors are swallowed and the previous state is retained.

    Args:
        client: Initialised EngineClient.
        player_id: Player character ID to poll reputation for.
        interval_s: Poll interval in seconds. Defaults to 3.0.
    """

    def __init__(
        self,
        client: EngineClient,
        player_id: str,
        interval_s: float = 3.0,
    ) -> None:
        self._client = client
        self._player_id = player_id
        self._interval = interval_s

        self._lock = threading.Lock()
        self._state: ObjectiveState = _INITIAL_STATE
        # Frozen once a demo faction first crosses WIN_STANDING_THRESHOLD (S7.3).
        self._first_allied_faction: str | None = None

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background polling daemon thread. Safe to call once."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def get_state(self) -> ObjectiveState:
        """Return the latest ObjectiveState snapshot (thread-safe, returns copy).

        Returns:
            ObjectiveState with current faction standings, iron_legion controls,
            and outcome ("win", "lose", or None). Empty until first poll completes.
        """
        with self._lock:
            return self._state

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: immediate first fetch, then interval-based."""
        self._poll_once()
        while not self._stop_event.wait(self._interval):
            self._poll_once()

    def _poll_once(self) -> None:
        """Fetch reputation and CONTROLS edges, evaluate conditions, update state.

        Swallows all exceptions so a transient error never crashes the render loop.
        On error, the previous ObjectiveState is retained unchanged.
        """
        try:
            reputation = self._client.get_npc_reputation(self._player_id)
            controls_edges = self._client.get_graph_edges(
                "CONTROLS", src_id=LOSE_FACTION_ID
            )
            controlled_locations = [
                edge.get("dst_id", "")
                for edge in controls_edges
                if edge.get("dst_id")
            ]
            new_state = evaluate_game_end(
                reputation,
                controlled_locations,
                arc_faction=self._first_allied_faction,
            )
            # Freeze the first allied faction once any demo faction crosses threshold.
            if self._first_allied_faction is None:
                detected = detect_first_allied_faction(new_state.faction_standings)
                if detected is not None:
                    self._first_allied_faction = detected
            with self._lock:
                self._state = new_state
        except Exception as exc:
            print(f"[GameEndPoller] error: {exc}", file=sys.stderr)
