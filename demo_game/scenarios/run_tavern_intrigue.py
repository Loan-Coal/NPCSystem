"""
Module: run_tavern_intrigue
Layer: demo_game (external client)
Purpose: Scripted tavern-intrigue demo runner. Plays a 5-beat story arc using the
         tavern eval world (tw_ prefix). Showcases: voice distinctiveness, event
         propagation reshaping NPC knowledge, and knowledge_state=rumour hedging.

Usage:
    make demo-tavern                    # live run (calls LLM, warms cache)
    make demo-tavern ARGS=--dry-run     # print scene sequence, no API calls
    make demo-tavern ARGS=--cached      # read-only cache; error on miss

Story:
    The Tarnished Flagon. A crossroads where rumours are the only currency.
    A merchant's purse is snatched. The innkeeper saw it happen. The wandering
    bard heard it second-hand. Each voice is shaped by who they are — not just
    what they know.

Requires:
    - docker-compose services running
    - Tavern world seeded: make seed-tavern-world
    - .env.demo with NPC_BASE_URL, NPC_API_KEY
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from demo_game.client import EngineClient
from demo_game.config import get_demo_config

# ---------------------------------------------------------------------------
# Cache — keyed by npc_id + player_input, stored in .cache/tavern/
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CACHE_DIR = _REPO_ROOT / ".cache" / "tavern"


class LLMCache:
    """Hash-keyed disk cache for LLM dialogue responses."""

    class CacheMissError(RuntimeError):
        pass

    def __init__(self, readonly: bool = False) -> None:
        self.readonly = readonly
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _key(self, npc_id: str, player_input: str) -> str:
        raw = f"{npc_id}:{player_input}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, npc_id: str, player_input: str) -> dict | None:
        path = _CACHE_DIR / f"{self._key(npc_id, player_input)}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    def put(self, npc_id: str, player_input: str, response: dict) -> None:
        if self.readonly:
            raise LLMCache.CacheMissError(
                f"Cache miss for npc={npc_id!r} input={player_input[:40]!r} "
                "and --cached flag is set. Run without --cached to warm the cache."
            )
        path = _CACHE_DIR / f"{self._key(npc_id, player_input)}.json"
        path.write_text(json.dumps(response, indent=2))


# ---------------------------------------------------------------------------
# Scene primitives
# ---------------------------------------------------------------------------


@dataclass
class Scene:
    """A single scripted action in the demo timeline."""
    name: str
    delay_before_ms: int = 0


@dataclass
class NarratorCue(Scene):
    """Print a narration line to stdout."""
    text: str = ""

    def execute(self, runner: "TavernDemoRunner") -> None:
        runner.print_cue(self.text)


@dataclass
class SeedCheck(Scene):
    """Verify a required NPC exists before the scene starts."""
    npc_id: str = ""

    def execute(self, runner: "TavernDemoRunner") -> None:
        runner.print_step(f"Verifying seed: {self.npc_id}")
        if runner.dry_run:
            return
        try:
            resp = runner.client._http.get(
                f"/v1/graph/nodes/Character/{self.npc_id}", timeout=5.0
            )
            if resp.status_code == 404:
                raise RuntimeError(
                    f"{self.npc_id} not found in graph. "
                    "Run: make seed-tavern-world"
                )
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Seed check failed: {exc}") from exc
        runner.print_ok(f"{self.npc_id} present in graph")


@dataclass
class EventFire(Scene):
    """Update world state active_conditions."""
    epoch: str = "age_of_peace"
    active_conditions: list[str] = field(default_factory=list)

    def execute(self, runner: "TavernDemoRunner") -> None:
        runner.print_step(f"Firing world event: active_conditions={self.active_conditions}")
        if runner.dry_run:
            return
        runner.client.put_world_state(epoch=self.epoch, active_conditions=self.active_conditions)
        runner.print_ok("World state updated")


@dataclass
class ClockTick(Scene):
    """Advance the gossip clock by N ticks."""
    delta_ticks: int = 1

    def execute(self, runner: "TavernDemoRunner") -> None:
        runner.print_step(f"Advancing gossip clock +{self.delta_ticks} tick(s)")
        if runner.dry_run:
            return
        runner.client.advance_clock(delta_ticks=self.delta_ticks)
        runner.print_ok("Clock advanced")


@dataclass
class DialogueBeat(Scene):
    """Send a player line and print the NPC response (cached or live)."""
    npc_id: str = ""
    player_input: str = ""
    label: str = ""

    def execute(self, runner: "TavernDemoRunner") -> None:
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
# Scene list — Tavern Intrigue
# Story: theft event → innkeeper (witness) → merchant (rumour) → wanderer (hearsay)
# Features: voice distinctiveness, event reshapes knowledge, Rule 9 gossip hedging
# ---------------------------------------------------------------------------
SCENES: list[Scene] = [
    NarratorCue(
        name="intro",
        text="=== Tavern Intrigue — NPC Voice & Knowledge Demo ===",
    ),
    SeedCheck(
        name="seed_check_innkeeper",
        delay_before_ms=500,
        npc_id="tw_innkeeper",
    ),
    NarratorCue(
        name="world_cue",
        delay_before_ms=1000,
        text="[NARRATION] The Prancing Goat Inn. Spring. Everyone passes through — stories travel faster than carts.",
    ),
    # Beat 1: Innkeeper before the theft — establishes voice (warm-but-efficient)
    NarratorCue(
        name="pre_innkeeper_cue_1",
        delay_before_ms=500,
        text="[NARRATION] Gwenna the innkeeper — efficient, commerce-first. Ask what she's noticed.",
    ),
    DialogueBeat(
        name="beat_1_innkeeper_before",
        delay_before_ms=500,
        npc_id="tw_innkeeper",
        label="Gwenna (Innkeeper)",
        player_input="What's the talk tonight?",
    ),
    # Beat 2: Wanderer before theft — storyteller voice
    NarratorCue(
        name="pre_wanderer_cue_1",
        delay_before_ms=2000,
        text="[NARRATION] Zephyrin the bard — every answer is a story. Same question, completely different voice.",
    ),
    DialogueBeat(
        name="beat_2_wanderer_before",
        delay_before_ms=500,
        npc_id="tw_wanderer",
        label="Zephyrin (Bard)",
        player_input="What's the talk tonight?",
    ),
    # Event: theft discovered
    NarratorCue(
        name="event_cue",
        delay_before_ms=2000,
        text="[NARRATION] A merchant's purse vanishes. Gwenna saw it happen. The bard only heard.",
    ),
    EventFire(
        name="theft_event",
        delay_before_ms=1000,
        epoch="age_of_peace",
        active_conditions=["theft_at_market"],
    ),
    ClockTick(name="tick_1", delay_before_ms=1500, delta_ticks=1),
    ClockTick(name="tick_2", delay_before_ms=1000, delta_ticks=1),
    # Beat 3: Innkeeper after theft — witnessed it directly (no hedging)
    NarratorCue(
        name="pre_innkeeper_cue_2",
        delay_before_ms=1000,
        text="[NARRATION] Ask Gwenna again — she witnessed it. Direct knowledge, no uncertainty.",
    ),
    DialogueBeat(
        name="beat_3_innkeeper_after",
        delay_before_ms=500,
        npc_id="tw_innkeeper",
        label="Gwenna (after theft)",
        player_input="Did you hear about the theft at the market?",
    ),
    # Beat 4: Wanderer — heard it second-hand (Rule 9: hedging)
    NarratorCue(
        name="pre_wanderer_cue_2",
        delay_before_ms=2000,
        text="[NARRATION] Zephyrin — same event, second-hand. He wasn't there. Watch the hedging.",
    ),
    DialogueBeat(
        name="beat_4_wanderer_after",
        delay_before_ms=500,
        npc_id="tw_wanderer",
        label="Zephyrin (after theft)",
        player_input="You hear about the theft?",
    ),
    # Beat 5: Merchant — minimised rumour (distortion_level=25, minimisation)
    NarratorCue(
        name="pre_merchant_cue",
        delay_before_ms=2000,
        text="[NARRATION] Corvus the merchant — heard about it, downplays it. Distorted rumour.",
    ),
    DialogueBeat(
        name="beat_5_merchant",
        delay_before_ms=500,
        npc_id="tw_merchant",
        label="Corvus (Merchant)",
        player_input="I heard there was some trouble at the market?",
    ),
    NarratorCue(
        name="outro",
        delay_before_ms=1000,
        text="=== Tavern demo complete. Same event — three voices, three accounts. ===",
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class TavernDemoRunner:
    """Executes the tavern intrigue demo scene list."""

    def __init__(self, dry_run: bool = False, cached: bool = False) -> None:
        self.dry_run = dry_run
        self.cache = LLMCache(readonly=cached)
        cfg = get_demo_config()
        self.client: EngineClient = EngineClient(
            base_url=cfg.NPC_BASE_URL,
            api_key=cfg.NPC_API_KEY,
        )

    def run(self) -> None:
        """Execute all scenes in order."""
        import time as _time
        start = _time.monotonic()
        skip_delays = self.dry_run or self.cache.readonly
        for scene in SCENES:
            if scene.delay_before_ms and not skip_delays:
                _time.sleep(scene.delay_before_ms / 1000)
            scene.execute(self)
        elapsed = _time.monotonic() - start
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
    parser = argparse.ArgumentParser(description="NPCSystem tavern intrigue demo runner")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print scene sequence without API calls.")
    parser.add_argument("--cached", action="store_true",
                        help="Read-only cache; error on miss. Use for recording.")
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = _parse_args()
    if args.dry_run and args.cached:
        print("Error: --dry-run and --cached are mutually exclusive.", file=sys.stderr)
        sys.exit(1)
    mode = "DRY-RUN" if args.dry_run else ("CACHED" if args.cached else "LIVE")
    print(f"[tavern_demo] mode={mode}")
    runner = TavernDemoRunner(dry_run=args.dry_run, cached=args.cached)
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
