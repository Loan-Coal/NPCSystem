"""
Module: emotion_poller
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Background daemon thread that polls GET /v1/npc/{npc_id}/emotion on a
         fixed interval and exposes the current emotion label and valence thread-safely.
         Optionally tracks a second (pair) NPC to surface mood-contagion data for
         EmotionPanelWidget (EXP-224).  Back-compatible: pair_npc_id defaults to None
         so existing single-NPC callers (game_window) are unaffected.
         Mirrors the WorldStatePoller pattern so GameWindow can show live mood data
         without blocking the render loop.
Dependencies: threading, sys, demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

_logger = logging.getLogger(__name__)


class EmotionPoller:
    """Background daemon thread that periodically polls the NPC emotion endpoint.

    Polls ``GET /v1/npc/{npc_id}/emotion`` every ``interval_s`` seconds for the
    currently active NPC. The latest label and valence are stored thread-safely
    and returned on each call to ``get_emotion()``.

    Optionally tracks a second "pair" NPC (EXP-224 mood-contagion visualiser).
    When ``pair_npc_id`` is provided, each poll also fetches that NPC's emotion
    and stores it under ``get_pair_emotion()``.  Default is ``None`` so all
    existing single-NPC callers (game_window) are untouched.

    Calling ``set_active_npc()`` clears the cached state and triggers an
    immediate re-poll, so the badge updates instantly on NPC switch.

    Exceptions during polling are swallowed and logged as WARNING so a transient
    network error never crashes the render loop.

    Args:
        client: Initialised EngineClient.
        interval_s: Poll interval in seconds. Defaults to 5.0.
        pair_npc_id: Optional second NPC id for contagion tracking. Defaults to None.
    """

    def __init__(
        self,
        client: EngineClient,
        interval_s: float = 5.0,
        pair_npc_id: str | None = None,
    ) -> None:
        self._client = client
        self._interval = interval_s

        self._lock = threading.Lock()
        self._npc_id: str | None = None
        self._label: str = ""
        self._valence: float = 0.0
        self._arousal: float = 0.0

        # Pair NPC state (EXP-224)
        self._pair_npc_id: str | None = pair_npc_id
        self._pair_label: str = ""
        self._pair_valence: float = 0.0
        self._pair_arousal: float = 0.0

        # Signals the polling loop to fire immediately (NPC switch or start).
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
        """Switch the target NPC, clear cached emotion, and trigger an immediate poll.

        Args:
            npc_id: New active NPC ID, or None to stop polling.
        """
        with self._lock:
            self._npc_id = npc_id
            self._label = ""
            self._valence = 0.0
            self._arousal = 0.0
        self._immediate.set()

    def get_emotion(self) -> tuple[str, float, float]:
        """Return the latest (label, valence, arousal) snapshot for the active NPC.

        Thread-safe. Returns empty defaults until the first successful poll.

        Returns:
            Tuple of (label_str, valence_float, arousal_float). All are
            empty/zero until the first successful poll completes for the
            current NPC.
        """
        with self._lock:
            return self._label, self._valence, self._arousal

    def get_pair_emotion(self) -> tuple[str, float, float]:
        """Return the latest (label, valence, arousal) for the contagion-pair NPC.

        Thread-safe. Returns ('', 0.0, 0.0) when no pair is configured or
        no successful poll has completed yet.

        Returns:
            Tuple of (label_str, valence_float, arousal_float).
        """
        with self._lock:
            return self._pair_label, self._pair_valence, self._pair_arousal

    def set_pair_npc_id(self, pair_npc_id: str | None) -> None:
        """Change the contagion-pair NPC being tracked and clear stale data.

        Args:
            pair_npc_id: New pair NPC id, or None to stop tracking a pair.
        """
        with self._lock:
            self._pair_npc_id = pair_npc_id
            self._pair_label = ""
            self._pair_valence = 0.0
            self._pair_arousal = 0.0

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
        """Fetch emotion for the active NPC (and pair NPC if set) under lock.

        Silently swallows all exceptions — a poll failure should never crash
        the render loop. Discards the primary result if the NPC switched mid-request.
        Pair poll failures are also swallowed independently so a failing pair
        endpoint never affects primary NPC display.
        """
        with self._lock:
            npc_id = self._npc_id
            pair_npc_id = self._pair_npc_id
        if npc_id is None:
            return
        self._poll_primary(npc_id)
        if pair_npc_id is not None:
            self._poll_pair(pair_npc_id)

    def _poll_primary(self, npc_id: str) -> None:
        """Fetch and store emotion for the primary active NPC.

        Args:
            npc_id: NPC id to fetch. Snapshot taken before the HTTP request.
        """
        try:
            data = self._client.get_npc_emotion(npc_id)
            if data is None:
                return
            label = str(data.get("label", ""))
            valence = float(data.get("valence", 0.0))
            arousal = float(data.get("arousal", 0.0))
            with self._lock:
                if self._npc_id == npc_id:  # discard if NPC switched mid-request
                    self._label = label
                    self._valence = valence
                    self._arousal = arousal
        except Exception as exc:
            _logger.warning("poll error: %s", exc)

    def _poll_pair(self, pair_npc_id: str) -> None:
        """Fetch and store emotion for the contagion-pair NPC (EXP-224).

        Failures are swallowed independently; pair data stays empty on error.

        Args:
            pair_npc_id: Pair NPC id to fetch.
        """
        try:
            data = self._client.get_npc_emotion(pair_npc_id)
            if data is None:
                return
            label = str(data.get("label", ""))
            valence = float(data.get("valence", 0.0))
            arousal = float(data.get("arousal", 0.0))
            with self._lock:
                if self._pair_npc_id == pair_npc_id:
                    self._pair_label = label
                    self._pair_valence = valence
                    self._pair_arousal = arousal
        except Exception as exc:
            _logger.warning("pair poll error npc=%s: %s", pair_npc_id, exc)

