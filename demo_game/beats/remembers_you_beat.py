"""
Module: remembers_you_beat
Layer: demo_game
Purpose: RemembersYouBeat demo scene — fetches NPC→player RELATES_TO edge and fires
         a "do you remember me?" dialogue turn to showcase cross-session memory.
Dependencies: demo_game.runners.run_scenes (Scene base), demo_game.client (EngineClient)
Used by: demo_game.runners.run
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from demo_game.runners.run_scenes import Scene

if TYPE_CHECKING:
    from demo_game.runners.run import DemoRunner

# ---------------------------------------------------------------------------
# Module-level constant (not an LLM prompt template — a demo client string)
# ---------------------------------------------------------------------------
_MEMORY_MESSAGE: str = "Do you remember the last time we spoke?"


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

@dataclass
class RemembersYouBeat(Scene):
    """Fetch the NPC→player RELATES_TO edge and fire a memory-recall dialogue.

    Steps:
    1. Print step header.
    2. Return immediately on dry_run.
    3. Call get_npc_relationship(npc_id, player_id).
    4. If None: print skip message and return.
    5. Print relationship values (trust, fear, affection, interaction_count).
    6. Post dialogue with _MEMORY_MESSAGE.
    7. Print the first 120 chars of npc_response.

    No try/except — errors propagate per standard scene contract.
    """

    npc_id: str = "mira_innkeeper"
    player_id: str = "player_demo"

    def execute(self, runner: DemoRunner) -> None:
        """Run the remembers-you beat against the engine.

        Args:
            runner: DemoRunner providing client, print helpers, and dry_run flag.
        """
        runner.print_step(
            f"[MEMORY] {self.npc_id} — checking relationship with {self.player_id}"
        )
        if runner.dry_run:
            return

        rel = runner.client.get_npc_relationship(self.npc_id, self.player_id)
        if rel is None:
            runner.print_ok(
                "[skip] No prior relationship edge — run demo again after first session"
            )
            return

        trust: int = rel.get("trust", 0)
        fear: int = rel.get("fear", 0)
        affection: int = rel.get("affection", 0)
        interactions: int = rel.get("interaction_count", 0)
        runner.print_ok(
            f"[relation] trust={trust} fear={fear} "
            f"affection={affection} interactions={interactions}"
        )

        response = runner.client.post_dialogue(
            player_id=self.player_id,
            npc_id=self.npc_id,
            player_message=_MEMORY_MESSAGE,
        )
        npc_text: str = response.get("npc_response", "")
        runner.print_ok(f"[memory] {self.npc_id}: {npc_text[:120]}")
