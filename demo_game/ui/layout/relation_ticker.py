"""
Module: relation_ticker
Layer: demo_game.ui
Purpose: Polls the relationship API for the active NPC→player_demo edge and surfaces
         trust/fear/affection deltas in the demo UI status overlay.
Dependencies: demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RELATION_POLL_TTL_S: float = 4.0
PLAYER_ID: str = "player_demo"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RelationSnapshot:
    """Immutable snapshot of a single RELATES_TO edge read.

    Attributes:
        trust: Trust level from the edge properties.
        fear: Fear level from the edge properties.
        affection: Affection level from the edge properties.
        interaction_count: Number of recorded interactions.
    """

    trust: int
    fear: int
    affection: int
    interaction_count: int


# ---------------------------------------------------------------------------
# RelationTicker
# ---------------------------------------------------------------------------


class RelationTicker:
    """Polls the NPC relationship API with TTL caching and computes deltas.

    Deltas are relative to the baseline set on first fetch (or after
    reset_baseline). Best-effort: errors are swallowed so the frame loop
    is never interrupted.

    Args:
        client: EngineClient instance used to fetch relationship data.
    """

    def __init__(self, client: EngineClient) -> None:
        self._client = client
        self._baseline: dict[str, RelationSnapshot] = {}
        self._current: dict[str, RelationSnapshot] = {}
        self._last_poll: dict[str, float] = {}

    def tick(self, npc_id: str) -> None:
        """Poll relationship data for npc_id if the TTL has expired.

        On the first successful fetch for a given NPC, the baseline is set
        to the fetched snapshot. Subsequent ticks update _current only.
        EngineClientError is swallowed — ticker is best-effort.

        Args:
            npc_id: NPC character node ID whose relationship to poll.
        """
        now = time.monotonic()
        last = self._last_poll.get(npc_id, -RELATION_POLL_TTL_S - 1.0)
        if now - last < RELATION_POLL_TTL_S:
            return

        try:
            data = self._client.get_npc_relationship(npc_id, PLAYER_ID)
        except Exception:  # noqa: BLE001 — intentional best-effort swallow
            return

        if data is None:
            return

        self._last_poll[npc_id] = now
        snap = RelationSnapshot(
            trust=int(data.get("trust", 0)),
            fear=int(data.get("fear", 0)),
            affection=int(data.get("affection", 0)),
            interaction_count=int(data.get("interaction_count", 0)),
        )
        self._current[npc_id] = snap
        if npc_id not in self._baseline:
            self._baseline[npc_id] = snap

    def get_delta_text(self, npc_id: str) -> str | None:
        """Return a formatted delta string comparing current vs baseline.

        Returns all three fields (trust, fear, affection) always, formatted
        with explicit sign. Example: ``"trust +2  fear +0  affection +1"``.

        Args:
            npc_id: NPC character node ID to compute deltas for.

        Returns:
            Formatted delta string, or None if no data has been fetched yet.
        """
        base = self._baseline.get(npc_id)
        curr = self._current.get(npc_id)
        if base is None or curr is None:
            return None

        def _fmt(label: str, delta: int) -> str:
            sign = "+" if delta >= 0 else ""
            return f"{label} {sign}{delta}"

        parts = [
            _fmt("trust", curr.trust - base.trust),
            _fmt("fear", curr.fear - base.fear),
            _fmt("affection", curr.affection - base.affection),
        ]
        return "  ".join(parts)

    def reset_baseline(self, npc_id: str) -> None:
        """Promote current snapshot to baseline for npc_id.

        Call this when the player switches NPC so deltas reflect changes
        since the new selection, not stale deltas from a prior NPC session.

        Args:
            npc_id: NPC character node ID whose baseline to reset.
        """
        curr = self._current.get(npc_id)
        if curr is not None:
            self._baseline[npc_id] = curr
