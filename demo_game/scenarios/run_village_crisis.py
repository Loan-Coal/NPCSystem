"""
Module: run_village_crisis
Layer: demo_game (external client)
Purpose: Scripted village-crisis demo runner. Plays a 5-beat story arc using the
         village eval world (vw_ prefix). Showcases: active_conditions world state
         anchoring, multi-NPC world awareness, event propagation, and gossip hedging.

Usage:
    make demo-village                    # live run (calls LLM, warms cache)
    make demo-village ARGS=--dry-run     # print scene sequence, no API calls
    make demo-village ARGS=--cached      # read-only cache; error on miss

Story:
    The village of Ashford, one week after the harvest failed. A crop blight
    spreads through the south fields. Then bandits strike. The same event passes
    through four different voices — direct witness, authority, rumour, and evasion.

Requires:
    - docker-compose services running
    - Village world seeded: make seed-village-world
    - .env.demo with NPC_BASE_URL, NPC_API_KEY
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from demo_game.client import EngineClient
from demo_game.config import get_demo_config

# ---------------------------------------------------------------------------
# Cache — keyed by npc_id + player_input, stored in .cache/village/
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CACHE_DIR = _REPO_ROOT / ".cache" / "village"


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

    def execute(self, runner: "VillageDemoRunner") -> None:
        runner.print_cue(self.text)


@dataclass
class SeedCheck(Scene):
    """Verify a required graph node exists before the scene starts."""
    npc_id: str = ""
    check_type: str = "npc"

    def execute(self, runner: "VillageDemoRunner") -> None:
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
                    "Run: make seed-village-world"
                )
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Seed check failed: {exc}") from exc
        runner.print_ok(f"{self.npc_id} present in graph")


@dataclass
class EventFire(Scene):
    """Update world state or fire an event by upserting active_conditions."""
    epoch: str = "age_of_peace"
    active_conditions: list[str] = field(default_factory=list)

    def execute(self, runner: "VillageDemoRunner") -> None:
        runner.print_step(f"Firing world event: active_conditions={self.active_conditions}")
        if runner.dry_run:
            return
        runner.client.put_world_state(epoch=self.epoch, active_conditions=self.active_conditions)
        runner.print_ok("World state updated")


@dataclass
class ClockTick(Scene):
    """Advance the gossip clock by N ticks."""
    delta_ticks: int = 1

    def execute(self, runner: "VillageDemoRunner") -> None:
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

    def execute(self, runner: "VillageDemoRunner") -> None:
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
# Scene list — Village Crisis
# Story: crop blight (world state) → bandit raid (event) → knowledge propagates
# Features: active_conditions anchoring, event knowledge, gossip hedging (Rule 9)
# ---------------------------------------------------------------------------
SCENES: list[Scene] = [
    NarratorCue(
        name="intro",
        text="=== Village Crisis — NPC Knowledge Demo ===",
    ),
    SeedCheck(
        name="seed_check_elder",
        delay_before_ms=500,
        npc_id="vw_elder",
    ),
    NarratorCue(
        name="world_state_cue",
        delay_before_ms=1000,
        text="[NARRATION] Ashford village, autumn. The south fields show a fungal blight.",
    ),
    # Beat 1: Elder knows about the blight (active_conditions → Rule 1 anchoring)
    NarratorCue(
        name="pre_elder_cue",
        delay_before_ms=500,
        text="[NARRATION] Ask Elder Aldwin — he has seen the field reports himself.",
    ),
    DialogueBeat(
        name="beat_1_elder",
        delay_before_ms=500,
        npc_id="vw_elder",
        label="Elder Aldwin",
        player_input="Elder, how are things in the village?",
    ),
    # Beat 2: Healer — different voice, same world awareness
    NarratorCue(
        name="pre_healer_cue",
        delay_before_ms=2000,
        text="[NARRATION] Healer Maret — precise, diagnostic. Same world state, different lens.",
    ),
    DialogueBeat(
        name="beat_2_healer",
        delay_before_ms=500,
        npc_id="vw_healer",
        label="Healer Maret",
        player_input="Are people in the village doing well?",
    ),
    # Event: bandit raid fires
    NarratorCue(
        name="event_cue",
        delay_before_ms=2000,
        text="[NARRATION] Overnight — bandits strike a farmstead. The guard was at the wrong end of the village.",
    ),
    EventFire(
        name="bandit_raid_event",
        delay_before_ms=1000,
        epoch="age_of_peace",
        active_conditions=["crop_blight", "bandit_threat"],
    ),
    ClockTick(name="tick_1", delay_before_ms=1500, delta_ticks=1),
    ClockTick(name="tick_2", delay_before_ms=1000, delta_ticks=1),
    # Beat 3: Guard — direct knowledge, terse voice (Rule 9: no hedging needed)
    NarratorCue(
        name="pre_guard_cue",
        delay_before_ms=1000,
        text="[NARRATION] Bren the guard — witnessed the aftermath. Direct knowledge, no hedging.",
    ),
    DialogueBeat(
        name="beat_3_guard",
        delay_before_ms=500,
        npc_id="vw_guard",
        label="Guard Bren",
        player_input="What happened last night?",
    ),
    # Beat 4: Farmer — heard it second-hand (Rule 9: rumour → epistemic hedging)
    NarratorCue(
        name="pre_farmer_cue",
        delay_before_ms=2000,
        text="[NARRATION] Jorin the farmer — heard the raid second-hand. Watch him hedge.",
    ),
    DialogueBeat(
        name="beat_4_farmer",
        delay_before_ms=500,
        npc_id="vw_farmer",
        label="Farmer Jorin",
        player_input="I heard there was a raid. What do you know about it?",
    ),
    # Beat 5: Fence — evasive, won't incriminate himself
    NarratorCue(
        name="pre_fence_cue",
        delay_before_ms=2000,
        text="[NARRATION] Silon the fence — same event, no direct knowledge, self-interest first.",
    ),
    DialogueBeat(
        name="beat_5_fence",
        delay_before_ms=500,
        npc_id="vw_fence",
        label="Silon (Fence)",
        player_input="You hear anything about last night's raid?",
    ),
    NarratorCue(
        name="outro",
        delay_before_ms=1000,
        text="=== Village demo complete. Same event — five different accounts. ===",
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class VillageDemoRunner:
    """Executes the village crisis demo scene list."""

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
    parser = argparse.ArgumentParser(description="NPCSystem village crisis demo runner")
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
    print(f"[village_demo] mode={mode}")
    runner = VillageDemoRunner(dry_run=args.dry_run, cached=args.cached)
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
