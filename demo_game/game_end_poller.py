"""
Module: game_end_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that periodically evaluates the H1 win/lose
         conditions by polling player reputation, iron_legion CONTROLS edges,
         gold balance, and clock state.
         Exposes the latest ObjectiveState thread-safely for the render loop.

H1 additions:
  - _seen_positive_gold latch: arms bankruptcy lose only after gold was once > 0.
  - _start_tick latch: captures the absolute clock tick on first successful poll
    to support relative DEADLINE_TICKS arithmetic.
  - _completed_quest_ids: polled per WIN_QUEST_CHAIN_IDS for the quest-chain path.
  - treaty_signed: polled via client.get_faction_treaties; degrades to False on error.

Dependencies: threading, sys, demo_game.client, demo_game.game_end_checker
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from demo_game.constants import WIN_QUEST_CHAIN_IDS
from demo_game.game_end_checker import (
    LOSE_FACTION_ID,
    ObjectiveState,
    detect_first_allied_faction,
    evaluate_game_end,
)

if TYPE_CHECKING:
    from demo_game.client import EngineClient

_logger = logging.getLogger(__name__)

_INITIAL_STATE = ObjectiveState(
    faction_standings={},
    iron_legion_controls=[],
    outcome=None,
)

_CHAR_NODE_TYPE = "Character"


class GameEndPoller:
    """Background daemon that polls win/lose conditions every interval_s seconds.

    Calls the following endpoints each cycle:
    - GET /v1/graph/characters/{player_id}/reputation → faction standings.
    - GET /v1/graph/edges/CONTROLS?src_id=iron_legion → legion lose.
    - GET /v1/graph/characters/{player_id} (Character node) → currency_balance.
    - GET /v1/clock/state → current_tick for deadline arithmetic.
    - GET /v1/admin/quests/{quest_id} for each WIN_QUEST_CHAIN_IDS quest → status.
    - GET /v1/admin/treaties/factions/{player_id} → treaty_signed flag.

    Latches:
    - _seen_positive_gold: set True the first time gold > 0; guards bankruptcy lose.
    - _start_tick: latched to current_tick on the first successful clock poll.

    Stores the result in ObjectiveState; transient errors are swallowed and the
    previous state is retained.

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

        # S7.3 arc tracking: frozen once a demo faction first crosses threshold.
        self._first_allied_faction: str | None = None

        # H1 bankruptcy latch: armed after gold was once > 0.
        self._seen_positive_gold: bool = False

        # H1 deadline latch: absolute tick from first successful clock poll.
        self._start_tick: int | None = None

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
        """Return the latest ObjectiveState snapshot (thread-safe).

        Returns:
            ObjectiveState with current standings, controls, and outcome.
            Empty until first poll completes.
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
        """Fetch all required data, evaluate conditions, update state.

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

            total_gold = self._fetch_gold()
            current_tick = self._fetch_current_tick()
            completed_quest_ids = self._fetch_completed_quests()
            treaty_signed = self._fetch_treaty_signed()

            self._update_latches(total_gold, current_tick)

            new_state = evaluate_game_end(
                reputation,
                controlled_locations,
                arc_faction=self._first_allied_faction,
                total_gold=total_gold,
                current_tick=current_tick,
                start_tick=self._start_tick,
                completed_quest_ids=completed_quest_ids,
                treaty_signed=treaty_signed,
                bankruptcy_armed=self._seen_positive_gold,
            )

            if self._first_allied_faction is None:
                detected = detect_first_allied_faction(new_state.faction_standings)
                if detected is not None:
                    self._first_allied_faction = detected

            with self._lock:
                self._state = new_state

        except Exception as exc:
            _logger.warning("poll error: %s", exc)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_gold(self) -> int | None:
        """Fetch the player's current gold balance via the Character node.

        Returns:
            Gold balance as int, or None on error.
        """
        try:
            char = self._client.get_node(_CHAR_NODE_TYPE, self._player_id)
            return int((char or {}).get("currency_balance") or 0)
        except Exception as exc:
            _logger.debug("gold fetch error: %s", exc)
            return None

    def _fetch_current_tick(self) -> int | None:
        """Fetch the current absolute clock tick.

        Returns:
            current_tick as int, or None on error.
        """
        try:
            clock = self._client.get_clock_state()
            return int(clock.get("current_tick") or 0)
        except Exception as exc:
            _logger.debug("clock fetch error: %s", exc)
            return None

    def _fetch_completed_quests(self) -> frozenset[str]:
        """Poll WIN_QUEST_CHAIN_IDS quests and return the completed subset.

        Returns:
            Frozenset of quest IDs that have status "completed".
        """
        completed: set[str] = set()
        for quest_id in WIN_QUEST_CHAIN_IDS:
            try:
                quest = self._client.get_quest(quest_id)
                if quest and quest.get("status") == "completed":
                    completed.add(quest_id)
            except Exception as exc:
                _logger.debug("quest fetch error (%s): %s", quest_id, exc)
        return frozenset(completed)

    def _fetch_treaty_signed(self) -> bool:
        """Check whether the player has at least one active treaty.

        Degrades gracefully to False when the endpoint is unavailable.

        Returns:
            True if any active treaty exists for the player character.
        """
        try:
            treaties = self._client.get_faction_treaties(self._player_id)
            return bool(treaties)
        except Exception as exc:
            _logger.debug("treaty fetch error: %s", exc)
            return False

    def _update_latches(self, total_gold: int | None, current_tick: int | None) -> None:
        """Update bankruptcy-armed and start-tick latches (non-reversible).

        Args:
            total_gold: Current gold balance.
            current_tick: Current absolute clock tick.
        """
        if not self._seen_positive_gold and total_gold is not None and total_gold > 0:
            self._seen_positive_gold = True
        if self._start_tick is None and current_tick is not None:
            self._start_tick = current_tick
