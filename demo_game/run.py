"""
Module: run
Layer: demo_game (external client)
Purpose: Scripted hackathon demo runner. Plays the exact docs/DEMO_SCRIPT.md
         scenario end-to-end via the engine HTTP API.

Usage:
    make demo-run              # live run (calls LLM, warms cache)
    make demo-run ARGS=--dry-run    # print scene sequence, no API calls
    make demo-run ARGS=--cached     # read-only cache; error on miss

Requires:
    - docker-compose services running (make demo-seed already done)
    - .env.demo with NPC_BASE_URL, NPC_API_KEY, (optionally) OPENAI_API_KEY
    - demo_game/requirements.txt installed in active venv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from demo_game.client import EngineClient
from demo_game.config import DemoConfig

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = _REPO_ROOT / ".cache" / "demo"


class LLMCache:
    """Hash-keyed disk cache for LLM dialogue responses.

    Key: sha256(npc_id + player_input).  Value: raw dialogue response dict.
    Cache miss with readonly=True raises CacheMissError.
    """

    class CacheMissError(RuntimeError):
        pass

    def __init__(self, readonly: bool = False) -> None:
        self.readonly = readonly
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _key(self, npc_id: str, player_input: str) -> str:
        raw = f"{npc_id}:{player_input}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, npc_id: str, player_input: str) -> dict[str, Any] | None:
        path = CACHE_DIR / f"{self._key(npc_id, player_input)}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    def put(self, npc_id: str, player_input: str, response: dict[str, Any]) -> None:
        if self.readonly:
            truncated = repr(player_input)[:40]
            raise LLMCache.CacheMissError(
                f"Cache miss for npc={npc_id!r} input={truncated} "
                "and --cached flag is set. Run without --cached to warm the cache."
            )
        path = CACHE_DIR / f"{self._key(npc_id, player_input)}.json"
        path.write_text(json.dumps(response, indent=2))


# ---------------------------------------------------------------------------
# Scene definitions
# ---------------------------------------------------------------------------
@dataclass
class Scene:
    """A single scripted action in the demo timeline."""

    name: str
    delay_before_ms: int = 0


@dataclass
class NarratorCue(Scene):
    """Print a narration cue to stdout (never calls the engine)."""

    text: str = ""

    def execute(self, runner: DemoRunner) -> None:
        runner.print_cue(self.text)


@dataclass
class SeedCheck(Scene):
    """Verify that a required KNOWS_ABOUT edge exists in the graph."""

    npc_id: str = "captain_sorn"
    required_edge_target: str = "northern_war_begins"

    def execute(self, runner: DemoRunner) -> None:
        runner.print_step(f"Verifying seed: {self.npc_id} KNOWS_ABOUT {self.required_edge_target}")
        if runner.dry_run:
            return
        edge = runner.client.get_edge("KNOWS_ABOUT", self.npc_id, self.required_edge_target)
        if edge is None:
            raise RuntimeError(
                f"{self.npc_id} missing KNOWS_ABOUT {self.required_edge_target}. "
                "Run: make demo-seed"
            )
        runner.print_ok(f"{self.npc_id} has KNOWS_ABOUT {self.required_edge_target}")


@dataclass
class EventFire(Scene):
    """Update world state to fire an event (epoch change + active conditions)."""

    epoch: str = "war"
    active_conditions: list[str] = field(default_factory=lambda: ["northern_war_active"])

    def execute(self, runner: DemoRunner) -> None:
        runner.print_step(f"Firing world event: epoch={self.epoch}")
        if runner.dry_run:
            return
        runner.client.put_world_state(epoch=self.epoch, active_conditions=self.active_conditions)
        runner.print_ok("World state updated")


@dataclass
class ClockTick(Scene):
    """Advance the gossip clock by N ticks."""

    delta_ticks: int = 1

    def execute(self, runner: DemoRunner) -> None:
        runner.print_step(f"Advancing gossip clock +{self.delta_ticks} tick(s)")
        if runner.dry_run:
            return
        runner.client.advance_clock(delta_ticks=self.delta_ticks)
        runner.print_ok("Clock advanced")


@dataclass
class DialogueBeat(Scene):
    """Send a player dialogue line and print the NPC response (cached or live)."""

    npc_id: str = ""
    player_input: str = ""
    label: str = ""

    def execute(self, runner: DemoRunner) -> None:
        display = self.label or self.npc_id
        runner.print_step(f"Dialogue [{display}]: {self.player_input!r:.60}")
        if runner.dry_run:
            return

        cached = runner.cache.get(self.npc_id, self.player_input)
        if cached:
            runner.print_ok(f"[cached] {display}: {cached.get('npc_response', '')[:80]}")
            return

        response = runner.client.post_dialogue(
            player_id="player",
            npc_id=self.npc_id,
            player_message=self.player_input,
        )
        runner.cache.put(self.npc_id, self.player_input, response)
        runner.print_ok(f"[live]   {display}: {response.get('npc_response', '')[:80]}")


# ---------------------------------------------------------------------------
# Scene list — fill in [FILL IN] values after docs/DEMO_SCRIPT.md is signed off
# ---------------------------------------------------------------------------
SCENES: list[Scene] = [
    NarratorCue(
        name="intro",
        text="=== NPCSystem Demo -- Hackathon June 6, 2026 ===",
    ),
    SeedCheck(
        name="seed_check",
        delay_before_ms=500,
        npc_id="captain_sorn",
        required_edge_target="northern_war_begins",
    ),
    NarratorCue(
        name="pre_event_cue",
        delay_before_ms=1000,
        text="[NARRATION] World is at peace. Captain Sorn knows something we don't -- yet.",
    ),
    EventFire(
        name="war_event",
        delay_before_ms=2000,
        epoch="war",
        active_conditions=["northern_war_active"],
    ),
    ClockTick(name="tick_1", delay_before_ms=1500, delta_ticks=1),
    ClockTick(name="tick_2", delay_before_ms=1000, delta_ticks=1),
    ClockTick(name="tick_3", delay_before_ms=1000, delta_ticks=1),
    NarratorCue(
        name="pre_sorn_cue",
        delay_before_ms=1000,
        text="[NARRATION] Ask Captain Sorn -- he has direct knowledge.",
    ),
    DialogueBeat(
        name="beat_1_sorn",
        delay_before_ms=500,
        npc_id="captain_sorn",
        label="Captain Sorn",
        player_input="Captain, what's happening in the north?",
    ),
    NarratorCue(
        name="pre_mira_cue",
        delay_before_ms=2000,
        text="[NARRATION] Now Mira -- she heard it second-hand.",
    ),
    DialogueBeat(
        name="beat_2_mira",
        delay_before_ms=500,
        npc_id="mira_innkeeper",
        label="Mira",
        player_input="Mira, have you heard any news from the north?",
    ),
    NarratorCue(
        name="pre_henryk_cue",
        delay_before_ms=2000,
        text="[NARRATION] Old Henryk -- third hand. The story has travelled far.",
    ),
    DialogueBeat(
        name="beat_3_henryk",
        delay_before_ms=500,
        npc_id="old_henryk",
        label="Old Henryk",
        player_input="Henryk, I heard there was trouble up north?",
    ),
    NarratorCue(
        name="sidebar_cue",
        delay_before_ms=1500,
        text="[NARRATION] Open the knowledge sidebar. Left: what Henryk thinks. Right: ground truth.",
    ),
    EventFire(
        name="market_fire",
        delay_before_ms=3000,
        epoch="war",
        active_conditions=["northern_war_active", "market_fire_active"],
    ),
    NarratorCue(
        name="pre_aldric_cue",
        delay_before_ms=1000,
        text="[NARRATION] Second event -- fire in Market Square. Watch Aldric's reaction.",
    ),
    DialogueBeat(
        name="beat_4_aldric",
        delay_before_ms=500,
        npc_id="aldric_merchant",
        label="Aldric",
        player_input="Aldric, are you alright? Was that fire near your stall?",
    ),
    NarratorCue(
        name="pre_lira_cue",
        delay_before_ms=2000,
        text="[NARRATION] Lira sees the same fire differently — same event, different emotion.",
    ),
    DialogueBeat(
        name="beat_5_lira",
        delay_before_ms=500,
        npc_id="lira_fence",
        label="Lira",
        player_input="Lira, did you hear about the fire? Seems like the kind of chaos that creates opportunity.",
    ),
    NarratorCue(
        name="outro",
        delay_before_ms=1000,
        text="=== Demo complete. 5 beats. Slides begin. ===",
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
class DemoRunner:
    """Executes the scripted demo scene list against the engine HTTP API."""

    def __init__(self, dry_run: bool = False, cached: bool = False) -> None:
        self.dry_run = dry_run
        self.cache = LLMCache(readonly=cached)
        cfg = DemoConfig()
        self.client: EngineClient = EngineClient(
            base_url=cfg.NPC_BASE_URL,
            api_key=cfg.NPC_API_KEY,
        )

    def run(self) -> None:
        """Execute all scenes in order."""
        start = time.monotonic()
        skip_delays = self.dry_run or self.cache.readonly
        for scene in SCENES:
            if scene.delay_before_ms and not skip_delays:
                time.sleep(scene.delay_before_ms / 1000)
            scene.execute(self)
        elapsed = time.monotonic() - start
        print(f"\n[done] {elapsed:.1f}s elapsed")

    def print_step(self, msg: str) -> None:
        print(f"  >  {msg}")

    def print_ok(self, msg: str) -> None:
        print(f"  ok {msg}")

    def print_cue(self, msg: str) -> None:
        bar = "-" * 60
        print(f"\n{bar}\n  {msg}\n{bar}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NPCSystem scripted demo runner")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print scene sequence without API calls.")
    parser.add_argument("--cached", action="store_true",
                        help="Read-only cache; error on miss. Use for final recording.")
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = _parse_args()

    if args.dry_run and args.cached:
        print("Error: --dry-run and --cached are mutually exclusive.", file=sys.stderr)
        sys.exit(1)

    mode = "DRY-RUN" if args.dry_run else ("CACHED" if args.cached else "LIVE")
    print(f"[demo_run] mode={mode}")

    runner = DemoRunner(dry_run=args.dry_run, cached=args.cached)
    try:
        runner.run()
    except LLMCache.CacheMissError as exc:
        print(f"\n[cache miss] {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[interrupted]")
        sys.exit(0)


if __name__ == "__main__":
    main()
