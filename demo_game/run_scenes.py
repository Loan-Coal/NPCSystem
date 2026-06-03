"""
Module: run_scenes
Layer: demo_game
Purpose: All Scene subclass definitions for the scripted demo runner. Extracted
         from run.py to keep each file under the 300-line limit.
Dependencies: demo_game.client, demo_game.dialogue_ws, demo_game.constants
Used by: demo_game.run

Note: file intentionally exceeds 300-line limit — see DEC-051.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from demo_game.constants import (
    BRIBE_GOLD_COST,
    BRIBE_STANDING_GAIN,
    PROPAGATED_REP_DELTA,
    PROPAGATED_REP_FACTION,
    PROPAGATED_REP_LOCATION,
)
from demo_game.dialogue_ws import dialogue_ws_worker

if TYPE_CHECKING:
    from demo_game.run import DemoRunner

_CHAR_TYPE = "Character"
_STANDING_CAP = 100


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

@dataclass
class Scene:
    """A single scripted action in the demo timeline."""

    name: str
    delay_before_ms: int = 0


# ---------------------------------------------------------------------------
# Narration / verification
# ---------------------------------------------------------------------------

@dataclass
class NarratorCue(Scene):
    """Print a narration cue to stdout (never calls the engine)."""

    text: str = ""

    def execute(self, runner: DemoRunner) -> None:
        """Print the narration bar."""
        runner.print_cue(self.text)


@dataclass
class SeedCheck(Scene):
    """Verify that a required KNOWS_ABOUT edge exists in the graph."""

    npc_id: str = "captain_sorn"
    required_edge_target: str = "northern_war_begins"

    def execute(self, runner: DemoRunner) -> None:
        """Abort with a helpful message if the required edge is absent."""
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


# ---------------------------------------------------------------------------
# World / clock
# ---------------------------------------------------------------------------

@dataclass
class EventFire(Scene):
    """Update world state to fire an event (epoch change + active conditions)."""

    epoch: str = "war"
    active_conditions: list[str] = field(default_factory=lambda: ["northern_war_active"])

    def execute(self, runner: DemoRunner) -> None:
        """PATCH world state on the engine."""
        runner.print_step(f"Firing world event: epoch={self.epoch}")
        if runner.dry_run:
            return
        runner.client.put_world_state(epoch=self.epoch, active_conditions=self.active_conditions)
        runner.print_ok("World state updated")


@dataclass
class ClockTick(Scene):
    """Advance the game clock by N ticks (triggers all engine ticks)."""

    delta_ticks: int = 1

    def execute(self, runner: DemoRunner) -> None:
        """POST clock advance."""
        runner.print_step(f"Advancing clock +{self.delta_ticks} tick(s)")
        if runner.dry_run:
            return
        runner.client.advance_clock(delta_ticks=self.delta_ticks)
        runner.print_ok("Clock advanced")


# ---------------------------------------------------------------------------
# Dialogue
# ---------------------------------------------------------------------------

@dataclass
class DialogueBeat(Scene):
    """Send a player dialogue line and print the NPC response (cached or live REST)."""

    npc_id: str = ""
    player_input: str = ""
    label: str = ""

    def execute(self, runner: DemoRunner) -> None:
        """Call POST /v1/dialogue, cache result."""
        display = self.label or self.npc_id
        runner.print_step(f"Dialogue [{display}]: {self.player_input!r:.60}")
        if runner.dry_run:
            return

        cached = runner.cache.get(self.npc_id, self.player_input)
        if cached:
            runner.print_ok(f"[cached] {display}: {cached.get('npc_response', '')[:80]}")
            return

        response = runner.client.post_dialogue(
            player_id="player_demo",
            npc_id=self.npc_id,
            player_message=self.player_input,
        )
        runner.cache.put(self.npc_id, self.player_input, response)
        runner.print_ok(f"[live]   {display}: {response.get('npc_response', '')[:80]}")


@dataclass
class StreamingDialogueBeat(Scene):
    """Stream a dialogue turn via WebSocket, printing tokens as they arrive.

    Falls back to the cache in --cached mode (prints without streaming).
    """

    npc_id: str = ""
    player_input: str = ""
    label: str = ""

    def execute(self, runner: DemoRunner) -> None:
        """Open WS, stream tokens to stdout, cache the full response."""
        display = self.label or self.npc_id
        runner.print_step(f"[stream] [{display}]: {self.player_input!r:.60}")
        if runner.dry_run:
            return

        cached = runner.cache.get(self.npc_id, self.player_input)
        if cached:
            runner.print_ok(f"[cached] {display}: {cached.get('npc_response', '')[:80]}")
            return

        result_q: queue.Queue = queue.Queue()
        payload = {
            "player_id": "player_demo",
            "npc_id": self.npc_id,
            "player_message": self.player_input,
        }
        t = threading.Thread(
            target=dialogue_ws_worker,
            args=(runner.client.ws_url, runner.client.api_key, payload, result_q),
            daemon=True,
        )
        t.start()

        print(f"  >>  {display}: ", end="", flush=True)
        tokens: list[str] = []
        while True:
            event_type, data = result_q.get()
            if event_type == "token":
                tokens.append(data)
                print(data, end="", flush=True)
            elif event_type == "done":
                print()
                break
            elif event_type == "error":
                print()
                raise RuntimeError(f"WS dialogue error for {self.npc_id}: {data}")
        t.join(timeout=5)

        full_text = "".join(tokens)
        runner.cache.put(self.npc_id, self.player_input, {"npc_response": full_text})


# ---------------------------------------------------------------------------
# Bribe / reputation
# ---------------------------------------------------------------------------

@dataclass
class BribeScene(Scene):
    """Pay BRIBE_GOLD_COST to improve player's standing with npc's faction."""

    player_id: str = "player_demo"
    npc_id: str = "lira_fence"
    faction_id: str = "thieves_guild"

    def execute(self, runner: DemoRunner) -> None:
        """Read player gold, validate, improve standing, deduct cost."""
        runner.print_step(
            f"Bribing {self.npc_id} -- paying {BRIBE_GOLD_COST}g for "
            f"+{BRIBE_STANDING_GAIN} standing with {self.faction_id}"
        )
        if runner.dry_run:
            return

        char = runner.client.get_node(_CHAR_TYPE, self.player_id) or {}
        gold = int(char.get("currency_balance") or 0)
        if gold < BRIBE_GOLD_COST:
            runner.print_ok(f"[skip] Not enough gold (have {gold}, need {BRIBE_GOLD_COST})")
            return

        reps = runner.client.get_npc_reputation(self.player_id)
        current = next(
            (int(r.get("standing") or 0) for r in reps if r.get("faction_id") == self.faction_id),
            0,
        )
        new_standing = min(_STANDING_CAP, current + BRIBE_STANDING_GAIN)
        runner.client.put_npc_reputation(self.player_id, self.faction_id, new_standing)
        runner.client.patch_node(_CHAR_TYPE, self.player_id, {"currency_balance": gold - BRIBE_GOLD_COST})
        runner.print_ok(
            f"Bribe paid -- {self.faction_id} standing: {current} -> {new_standing} "
            f"(gold {gold} -> {gold - BRIBE_GOLD_COST})"
        )


@dataclass
class ReputationDisplay(Scene):
    """Print the player's current standing with a faction."""

    player_id: str = "player_demo"
    faction_id: str = "thieves_guild"

    def execute(self, runner: DemoRunner) -> None:
        """Fetch and print the standing value."""
        runner.print_step(f"Reading {self.player_id} standing with {self.faction_id}")
        if runner.dry_run:
            return
        reps = runner.client.get_npc_reputation(self.player_id)
        standing = next(
            (int(r.get("standing") or 0) for r in reps if r.get("faction_id") == self.faction_id),
            None,
        )
        if standing is None:
            runner.print_ok(f"[info] No standing edge found for {self.faction_id}")
        else:
            runner.print_ok(f"[political] {self.player_id} <-> {self.faction_id}: standing={standing}")


# ---------------------------------------------------------------------------
# Emotion / state
# ---------------------------------------------------------------------------

@dataclass
class EmotionDisplay(Scene):
    """Print the current in-memory emotion snapshot for an NPC."""

    npc_id: str = ""

    def execute(self, runner: DemoRunner) -> None:
        """Call GET /v1/npc/{npc_id}/emotion and print the result."""
        runner.print_step(f"Reading {self.npc_id} emotion")
        if runner.dry_run:
            return
        emotion = runner.client.get_npc_emotion(self.npc_id)
        if not emotion:
            runner.print_ok(f"[info] No emotion snapshot for {self.npc_id}")
        else:
            label = emotion.get("label", "?")
            valence = emotion.get("valence", "?")
            arousal = emotion.get("arousal", "?")
            runner.print_ok(
                f"[emotion] {self.npc_id}: {label} "
                f"(valence={valence} arousal={arousal})"
            )


# ---------------------------------------------------------------------------
# Quest
# ---------------------------------------------------------------------------

@dataclass
class QuestDisplay(Scene):
    """Print the details of a quest node."""

    quest_id: str = "aldric_deliver_quest"

    def execute(self, runner: DemoRunner) -> None:
        """Fetch the quest by ID and print its status."""
        runner.print_step(f"Reading quest {self.quest_id}")
        if runner.dry_run:
            return
        quest = runner.client.get_quest(self.quest_id)
        if not quest:
            runner.print_ok(f"[info] Quest {self.quest_id} not found -- run make demo-seed")
        else:
            title = quest.get("title") or quest.get("description", "?")
            status = quest.get("status", "?")
            runner.print_ok(f"[quest] {title!r} [{status}]")


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

@dataclass
class MemoryConsolidate(Scene):
    """Trigger memory consolidation for an NPC from their session dialogue turns."""

    npc_id: str = ""
    player_id: str = "player_demo"

    def execute(self, runner: DemoRunner) -> None:
        """Call POST /v1/admin/memories/consolidate/{npc_id}."""
        runner.print_step(f"Consolidating {self.npc_id} session memory")
        if runner.dry_run:
            return
        game_time = {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
        memory_id = runner.client.consolidate_memory(self.npc_id, self.player_id, game_time)
        if memory_id:
            runner.print_ok(f"[memory] {self.npc_id}: Memory node created -- id={memory_id}")
        else:
            runner.print_ok(f"[memory] {self.npc_id}: Turn threshold not met (need more dialogue turns)")


# ---------------------------------------------------------------------------
# World feed
# ---------------------------------------------------------------------------

@dataclass
class WorldFeed(Scene):
    """Fetch and print the most recent engine events from the WORLD feed."""

    limit: int = 5
    event_type_filter: str | None = None

    def execute(self, runner: DemoRunner) -> None:
        """Call GET /v1/system/events and print each event."""
        runner.print_step(f"WORLD feed -- last {self.limit} events")
        if runner.dry_run:
            return
        events = runner.client.get_recent_events(limit=self.limit)
        if not events:
            runner.print_ok("[world] No events yet")
            return
        for evt in events:
            if self.event_type_filter and evt.get("event_type") != self.event_type_filter:
                continue
            etype = evt.get("event_type", "?")
            summary = evt.get("summary", "?")[:70]
            tick = evt.get("tick_id", "?")
            runner.print_ok(f"[world tick={tick}] {etype}: {summary}")


# ---------------------------------------------------------------------------
# Propagated reputation (S8.3)
# ---------------------------------------------------------------------------

@dataclass
class PropagatedReputationAct(Scene):
    """Commit a notable act at a location, seeding a gossip-propagatable reputation event.

    Calls the /adjust endpoint with location_id + tick_id so the engine creates a
    reputation_change Event node and seeds KNOWS_ABOUT edges for co-located NPCs.
    After a few clock ticks, distant NPCs (e.g. mira_innkeeper at loc_tavern) will
    receive the event via gossip propagation and greet the player accordingly.
    """

    player_id: str = "player_demo"
    faction_id: str = PROPAGATED_REP_FACTION
    delta: int = PROPAGATED_REP_DELTA
    location_id: str = PROPAGATED_REP_LOCATION

    def execute(self, runner: DemoRunner) -> None:
        """Adjust standing + seed reputation event; print new standing and tick_id used."""
        runner.print_step(
            f"[act] {self.player_id} {self.delta:+d} standing with {self.faction_id} "
            f"at {self.location_id} (gossip event seeded)"
        )
        if runner.dry_run:
            return

        clock = runner.client.get_clock_state()
        tick_id: int = clock.get("data", {}).get("current_tick", 1)

        result = runner.client.adjust_npc_reputation(
            self.player_id, self.faction_id, self.delta, self.location_id, tick_id
        )
        new_standing = result.get("data", {}).get("standing", "?")
        runner.print_ok(
            f"[reputation] {self.faction_id}: standing={new_standing} "
            f"(reputation_change event at {self.location_id}, tick={tick_id})"
        )


# ---------------------------------------------------------------------------
# Rumor gameplay arc (S10.4)
# ---------------------------------------------------------------------------

@dataclass
class SpreadRumorScene(Scene):
    """Plant a fabricated rumor into target_npc_id and capture the returned event_id.

    The event_id is stored on the runner as ``runner.planted_event_id`` so subsequent
    scenes (RumorTraceDisplay, CorrectRumorScene) can reference the same event.
    """

    target_npc_id: str = "lira_fence"
    rumor_text: str = ""
    severity: int = 70

    def execute(self, runner: DemoRunner) -> None:
        """POST /v1/admin/gossip/spread and capture event_id on runner."""
        runner.print_step(
            f"[rumor] Planting lie at {self.target_npc_id!r}: {self.rumor_text!r:.60}"
        )
        if runner.dry_run:
            return

        clock = runner.client.get_clock_state()
        tick_id: int = clock.get("data", {}).get("current_tick", 0)

        resp = runner.client.spread_rumor(
            target_npc_id=self.target_npc_id,
            rumor_text=self.rumor_text,
            severity=self.severity,
            tick_id=tick_id,
        )
        event_id: str = resp.get("data", {}).get("event_id", "")
        runner.planted_event_id = event_id  # type: ignore[attr-defined]
        runner.print_ok(f"[rumor] Planted — event_id={event_id!r} tick={tick_id}")


@dataclass
class RumorTraceDisplay(Scene):
    """Print the propagation chain for the most recently planted rumor.

    Reads ``runner.planted_event_id`` set by SpreadRumorScene.
    """

    def execute(self, runner: DemoRunner) -> None:
        """GET /v1/admin/gossip/trace/{event_id} and print the chain."""
        runner.print_step("[rumor] Tracing propagation chain")
        if runner.dry_run:
            return

        event_id: str = getattr(runner, "planted_event_id", "")
        if not event_id:
            runner.print_ok("[rumor] No planted_event_id on runner — skipping trace")
            return

        resp = runner.client.trace_rumor(event_id)
        chain: list[dict] = resp.get("data", {}).get("chain", [])
        if not chain:
            runner.print_ok("[rumor] Chain empty — rumor has not propagated yet")
            return
        for hop in chain:
            npc = hop.get("npc_id", "?")
            tick = hop.get("learned_at_tick", "?")
            state = hop.get("knowledge_state") or "believed"
            runner.print_ok(f"  hop: {npc} (tick={tick}, state={state})")


@dataclass
class CorrectRumorScene(Scene):
    """Mark one NPC's belief in the planted rumor as corrected.

    Reads ``runner.planted_event_id`` set by SpreadRumorScene.
    Corrected NPCs no longer reference the lie in dialogue; downstream NPCs are unaffected.
    """

    npc_id: str = "mira_innkeeper"

    def execute(self, runner: DemoRunner) -> None:
        """POST /v1/admin/gossip/correct for npc_id + planted event_id."""
        runner.print_step(f"[rumor] Correcting belief at {self.npc_id!r}")
        if runner.dry_run:
            return

        event_id: str = getattr(runner, "planted_event_id", "")
        if not event_id:
            runner.print_ok("[rumor] No planted_event_id on runner — skipping correction")
            return

        resp = runner.client.correct_rumor(npc_id=self.npc_id, event_id=event_id)
        corrected: bool = resp.get("data", {}).get("corrected", False)
        runner.print_ok(
            f"[rumor] {self.npc_id} corrected={corrected} (event_id={event_id!r})"
        )
