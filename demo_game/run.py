"""
Module: run
Layer: demo_game (external client)
Purpose: Scripted hackathon demo runner. Plays the docs/DEMO_SCRIPT.md scenario
         end-to-end via the engine HTTP API, covering all Phase 6 engine beats.

Usage:
    make demo-run              # live run (calls LLM, warms cache)
    make demo-run ARGS=--dry-run    # print scene sequence, no API calls
    make demo-run ARGS=--cached     # read-only cache; error on miss (recording)

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
from pathlib import Path
from typing import Any

from demo_game.client import EngineClient
from demo_game.config import DemoConfig
from demo_game.run_scenes import (
    BribeScene,
    ClockTick,
    DialogueBeat,
    EmotionDisplay,
    EventFire,
    MemoryConsolidate,
    NarratorCue,
    QuestDisplay,
    ReputationDisplay,
    Scene,
    SeedCheck,
    StreamingDialogueBeat,
    WorldFeed,
)
from npc_engine.engines.dialogue.prompt_builder import PROMPT_VERSION as _PROMPT_VERSION

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = _REPO_ROOT / ".cache" / "demo"


class LLMCache:
    """Hash-keyed disk cache for LLM dialogue responses.

    Key: sha256(npc_id + player_input + PROMPT_VERSION). Value: raw dialogue response dict.
    Cache miss with readonly=True raises CacheMissError.
    """

    class CacheMissError(RuntimeError):
        """Raised on a cache miss when --cached is set."""

    def __init__(self, readonly: bool = False) -> None:
        self.readonly = readonly
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _key(self, npc_id: str, player_input: str) -> str:
        raw = f"{npc_id}:{player_input}:{_PROMPT_VERSION}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, npc_id: str, player_input: str) -> dict[str, Any] | None:
        """Return the cached response dict or None on miss."""
        path = CACHE_DIR / f"{self._key(npc_id, player_input)}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    def put(self, npc_id: str, player_input: str, response: dict[str, Any]) -> None:
        """Write a response to cache; raises CacheMissError if readonly."""
        if self.readonly:
            truncated = repr(player_input)[:40]
            raise LLMCache.CacheMissError(
                f"Cache miss for npc={npc_id!r} input={truncated} "
                "and --cached flag is set. Run without --cached to warm the cache."
            )
        path = CACHE_DIR / f"{self._key(npc_id, player_input)}.json"
        path.write_text(json.dumps(response, indent=2))


# ---------------------------------------------------------------------------
# Scene list -- full Phase 6 coverage (all S6 engine beats)
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

    # -----------------------------------------------------------------------
    # ACT 1 -- Gossip chain (S6.0 + S6.4 streaming)
    # -----------------------------------------------------------------------
    NarratorCue(
        name="pre_event_cue",
        delay_before_ms=1000,
        text="[ACT 1] World at peace. Captain Sorn knows something we don't -- yet.",
    ),
    EventFire(
        name="war_event",
        delay_before_ms=2000,
        epoch="war",
        active_conditions=["northern_war_active"],
    ),
    NarratorCue(
        name="pre_tick_cue",
        delay_before_ms=500,
        text="[NARRATION] Clock advances. Gossip propagates: Sorn -> Mira -> Henryk.",
    ),
    ClockTick(name="tick_1", delay_before_ms=1000, delta_ticks=1),
    ClockTick(name="tick_2", delay_before_ms=500, delta_ticks=1),
    ClockTick(name="tick_3", delay_before_ms=500, delta_ticks=1),
    NarratorCue(
        name="pre_sorn_cue",
        delay_before_ms=1000,
        text="[NARRATION] Ask Captain Sorn -- streaming dialogue, direct knowledge.",
    ),
    StreamingDialogueBeat(
        name="beat_1_sorn",
        delay_before_ms=500,
        npc_id="captain_sorn",
        label="Captain Sorn",
        player_input="Captain, what's happening in the north?",
    ),
    NarratorCue(
        name="pre_mira_cue",
        delay_before_ms=2000,
        text="[NARRATION] Mira -- second-hand. Watch the faction name drift.",
    ),
    StreamingDialogueBeat(
        name="beat_2_mira",
        delay_before_ms=500,
        npc_id="mira_innkeeper",
        label="Mira",
        player_input="Mira, have you heard any news from the north?",
    ),
    NarratorCue(
        name="pre_henryk_cue",
        delay_before_ms=2000,
        text="[NARRATION] Old Henryk -- third hand, fully garbled. Open the KNOWLEDGE sidebar.",
    ),
    StreamingDialogueBeat(
        name="beat_3_henryk",
        delay_before_ms=500,
        npc_id="old_henryk",
        label="Old Henryk",
        player_input="Henryk, I heard there was trouble up north?",
    ),

    # -----------------------------------------------------------------------
    # ACT 2 -- Quest + market fire + emotion change (S6.1)
    # -----------------------------------------------------------------------
    NarratorCue(
        name="pre_quest_cue",
        delay_before_ms=2000,
        text="[ACT 2] Engine-generated quest: Aldric wants the ancient amulet returned.",
    ),
    QuestDisplay(
        name="quest_display",
        delay_before_ms=500,
        quest_id="aldric_deliver_quest",
    ),
    EventFire(
        name="market_fire",
        delay_before_ms=2000,
        epoch="war",
        active_conditions=["northern_war_active", "market_fire_active"],
    ),
    NarratorCue(
        name="pre_aldric_cue",
        delay_before_ms=1000,
        text="[NARRATION] Second event -- fire in Market Square. Aldric's emotion shifts.",
    ),
    StreamingDialogueBeat(
        name="beat_4_aldric",
        delay_before_ms=500,
        npc_id="aldric_merchant",
        label="Aldric",
        player_input="Aldric, are you alright? Was that fire near your stall?",
    ),
    EmotionDisplay(
        name="aldric_emotion",
        delay_before_ms=500,
        npc_id="aldric_merchant",
    ),

    # -----------------------------------------------------------------------
    # ACT 3 -- Bribe + political consequence (S6.2)
    # -----------------------------------------------------------------------
    NarratorCue(
        name="pre_bribe_cue",
        delay_before_ms=2000,
        text="[ACT 3] Bribe Lira -- player pays 20g, standing with Thieves' Guild improves.",
    ),
    BribeScene(
        name="bribe_lira",
        delay_before_ms=500,
        player_id="player_demo",
        npc_id="lira_fence",
        faction_id="thieves_guild",
    ),
    ReputationDisplay(
        name="standing_after_bribe",
        delay_before_ms=500,
        player_id="player_demo",
        faction_id="thieves_guild",
    ),
    NarratorCue(
        name="lira_response_cue",
        delay_before_ms=1000,
        text="[NARRATION] Lira's response after the bribe -- same chaos, different tone.",
    ),
    StreamingDialogueBeat(
        name="beat_5_lira",
        delay_before_ms=500,
        npc_id="lira_fence",
        label="Lira",
        player_input="Lira, did you hear about the fire? Seems like your kind of chaos.",
    ),

    # -----------------------------------------------------------------------
    # ACT 4 -- Memory recall (S6.3)
    # -----------------------------------------------------------------------
    NarratorCue(
        name="pre_memory_cue",
        delay_before_ms=2000,
        text="[ACT 4] Memory consolidation -- Mira's session turns become a permanent Memory node.",
    ),
    MemoryConsolidate(
        name="mira_memory",
        delay_before_ms=500,
        npc_id="mira_innkeeper",
        player_id="player_demo",
    ),

    # -----------------------------------------------------------------------
    # ACT 5 -- Military engine + WORLD feed (S6.5 + S6.0)
    # -----------------------------------------------------------------------
    NarratorCue(
        name="pre_military_cue",
        delay_before_ms=2000,
        text=(
            "[ACT 5] Military engine tick -- Iron Legion (strength 100) vs City Guard (60) "
            "at the barracks. One clock advance resolves the battle."
        ),
    ),
    ClockTick(name="military_tick", delay_before_ms=1000, delta_ticks=1),
    NarratorCue(
        name="pre_world_feed_cue",
        delay_before_ms=500,
        text="[NARRATION] WORLD feed -- battle event surfaced by the military engine.",
    ),
    WorldFeed(
        name="world_feed_battle",
        delay_before_ms=500,
        limit=8,
    ),

    NarratorCue(
        name="outro",
        delay_before_ms=1000,
        text="=== Demo complete. 5 acts. All Phase 6 beats covered. Slides begin. ===",
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
        """Print a step line."""
        print(f"  >  {msg}")

    def print_ok(self, msg: str) -> None:
        """Print a result line."""
        print(f"  ok {msg}")

    def print_cue(self, msg: str) -> None:
        """Print a narration bar."""
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
