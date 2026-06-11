"""
Module: proactive_dialogue_beat
Layer: demo_game
Purpose: ProactiveDialogueBeat demo scene — advances the clock one tick, fetches
         NPC-initiated pending intents for the player, and renders the first
         NPC-hail line. Degrades gracefully (no crash) when no intents are pending.
Dependencies: demo_game.run_scenes (Scene base), demo_game.client (EngineClient)
Used by: demo_game.run
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from demo_game.run_scenes import Scene

if TYPE_CHECKING:
    from demo_game.run import DemoRunner

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLAYER_ID: str = "player_demo"
_NO_PENDING_MSG: str = "[no pending] No NPC-initiated intents queued for this player"
_CLOCK_ADVANCE_TICKS: int = 1


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

@dataclass
class ProactiveDialogueBeat(Scene):
    """Advance the clock and surface the top NPC-initiated dialogue intent.

    Steps:
    1. Print step header.
    2. Return immediately on dry_run.
    3. Advance clock by _CLOCK_ADVANCE_TICKS (allows proactive engine to fire).
    4. Fetch pending intents via client.get_pending_intents(player_id).
    5. If empty: print _NO_PENDING_MSG and return (graceful no-op).
    6. Render the top intent: NPC id, intent_type, and message.

    No try/except — errors propagate per standard scene contract.
    """

    player_id: str = _PLAYER_ID

    def execute(self, runner: DemoRunner) -> None:
        """Run the proactive-dialogue beat.

        Args:
            runner: DemoRunner providing client, print helpers, and dry_run flag.
        """
        runner.print_step("[PROACTIVE] Advancing clock; checking for NPC-initiated intents")
        if runner.dry_run:
            return

        runner.client.advance_clock(delta_ticks=_CLOCK_ADVANCE_TICKS)

        intents: list[dict] = runner.client.get_pending_intents(self.player_id)
        if not intents:
            runner.print_ok(_NO_PENDING_MSG)
            return

        top = intents[0]
        npc_id: str = top.get("npc_id", "unknown")
        intent_type: str = top.get("intent_type", "unknown")
        message: str = top.get("message", "")
        runner.print_ok(
            f"[proactive] {npc_id} hails you [{intent_type}]: {message[:120]}"
        )
