"""
Module: determinism_beat
Layer: demo_game
Purpose: DeterminismBeat demo scene — calls POST /v1/batch/gossip_tick twice with
         the same tick_override and asserts seeds_used are identical, printing a
         two-column table to prove same-seed → same-distortion replay.
Dependencies: demo_game.runners.run_scenes (Scene base)
Used by: demo_game.runners.run
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from demo_game.runners.run_scenes import Scene

if TYPE_CHECKING:
    from demo_game.runners.run import DemoRunner


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DETERMINISM_TICK_OVERRIDE: int = 42
_DETERMINISM_NPC_IDS: list[str] = ["captain_sorn", "mira_innkeeper"]
_GOSSIP_TICK_PATH: str = "/v1/batch/gossip_tick"

_HEADER_WIDTH: int = 70
_COL_WIDTH: int = 20


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------


@dataclass
class DeterminismBeat(Scene):
    """Prove gossip-tick determinism by running the same tick_override twice.

    Steps:
    1. Print step header.
    2. Return immediately on dry_run.
    3. POST /v1/batch/gossip_tick twice with tick_override=42 and the demo pair.
    4. Extract seeds_used from both responses.
    5. Print a two-column table (run 1 seed | run 2 seed | match?).
    6. Assert seeds_match=True and print a confirmation line.

    No try/except — errors propagate per standard scene contract.
    """

    tick_override: int = _DETERMINISM_TICK_OVERRIDE
    npc_ids: list[str] = field(default_factory=lambda: list(_DETERMINISM_NPC_IDS))

    def execute(self, runner: DemoRunner) -> None:
        """Run the determinism proof beat against the engine.

        Args:
            runner: DemoRunner providing client, print helpers, and dry_run flag.
        """
        runner.print_cue(
            "[ACT 10] Determinism proof — same tick_override → same seeds"
        )
        runner.print_step(
            f"POST {_GOSSIP_TICK_PATH} × 2 with tick_override={self.tick_override}"
        )
        if runner.dry_run:
            return

        run1 = self._call_gossip_tick(runner)
        run2 = self._call_gossip_tick(runner)

        seeds1: dict[str, int] = run1.get("data", run1).get("seeds_used", {})
        seeds2: dict[str, int] = run2.get("data", run2).get("seeds_used", {})

        self._print_seed_table(runner, seeds1, seeds2)

        seeds_match = seeds1 == seeds2
        runner.print_ok(f"seeds_match={seeds_match}")
        assert seeds_match, (
            f"Determinism check FAILED: seeds differ between runs "
            f"for tick_override={self.tick_override}"
        )

    def _call_gossip_tick(self, runner: DemoRunner) -> dict:
        """POST one gossip tick and return the parsed JSON response.

        Args:
            runner: DemoRunner providing the HTTP client.

        Returns:
            Parsed JSON response dict from the engine.
        """
        resp = runner.client._client.post(
            _GOSSIP_TICK_PATH,
            json={
                "tick_override": self.tick_override,
                "npc_ids": self.npc_ids,
                "max_pairs": 1,
            },
            timeout=runner.client._graph_timeout,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _print_seed_table(
        runner: DemoRunner,
        seeds1: dict[str, int],
        seeds2: dict[str, int],
    ) -> None:
        """Print a two-column seed comparison table to stdout.

        Args:
            runner: DemoRunner providing print helpers.
            seeds1: seeds_used from the first gossip tick call.
            seeds2: seeds_used from the second gossip tick call.
        """
        all_keys = sorted(set(seeds1) | set(seeds2))
        runner.print_step(
            f"  {'pair':<{_COL_WIDTH}}  {'run1 seed':>{_COL_WIDTH}}  "
            f"{'run2 seed':>{_COL_WIDTH}}  match?"
        )
        runner.print_step("-" * _HEADER_WIDTH)
        for key in all_keys:
            s1 = seeds1.get(key, -1)
            s2 = seeds2.get(key, -1)
            match_str = "YES" if s1 == s2 else "NO"
            runner.print_step(
                f"  {key:<{_COL_WIDTH}}  {s1:>{_COL_WIDTH}}  "
                f"{s2:>{_COL_WIDTH}}  {match_str}"
            )
