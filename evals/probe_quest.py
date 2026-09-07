"""
Module: probe_quest
Layer: evals (eval harness — not part of src/)
Purpose: EngineProbe for the quest + quest_generation engines (measurement-remediation
         Phase 4, DEC-271). Generates quests for a fresh quest giver, drives them through
         offer/accept/evaluate, and measures conversion rates, slot-validity, and
         referential grounding. Also snapshots ISSUE-273's background leak (measured, not
         fixed): WorldStateQuestTrigger names every leaked draft to the seeded NPC
         `captain_sorn` (verified — ISSUE-273's own text), so bracketing that NPC's draft
         count across one repetition is a read-only tripwire for the leak recurring
         during a probe run, without this probe manufacturing epoch="war" conditions
         itself (the world's reset baseline is age_of_peace and this probe does not
         override it — forcing war epoch to reproduce the leak on demand would generate
         more of exactly the garbage ISSUE-273 already documents).
Dependencies: httpx, uuid, probe_protocol, scenario_adapter_utils, entity_scorer,
              graph_vocabulary (evals/)
Used by: probe_runner.PROBE_FACTORIES
Does NOT: import from src/npc_engine/, offer/accept/evaluate through the full player-
          facing QuestOfferService (that requires a title/objectives/reward body this
          probe does not author) — it uses the admin "simple" offer transition
          (POST /v1/admin/quests/{id}/offer) plus the player-facing accept/evaluate
          routes on the same quest_id. If those two lifecycle paths do not compose
          today (plausible: ISSUE-259, ISSUE-274 both already flag the quest lifecycle
          integration path as broken/stale), accept_rate and complete_rate simply read
          low or zero — an honest measurement, not a crash, and not a new issue filed
          speculatively on top of two already-open ones.

Slot-validity (DEC-271): only `target_id` is persisted onto a generated Quest node
(verified — quest_generation_engine.py's fills_raw.get("target") or .get("item") is the
only slot baked into a graph field; the rest survive only in the LLM-authored description
text). There is no generic "get node by id regardless of type" route, so validity is
checked by trying each plausible node type in turn until one responds 200.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable

import httpx

from entity_scorer import load_aliases, unsupported_entity_rate
from graph_vocabulary import fetch_vocabulary
from probe_protocol import EngineProbe
from scenario_adapter_utils import ADMIN_PREFIX, GRAPH_PREFIX, is_ok, now_iso

QuestProbeFactory = Callable[[httpx.Client], EngineProbe]

_ALIASES_PATH = Path(__file__).resolve().parent / "cases" / "entity_aliases.yaml"
_PLAUSIBLE_TARGET_TYPES: tuple[str, ...] = ("character", "item", "location", "event")
_BACKGROUND_LEAK_GIVER_ID: str = "captain_sorn"  # ISSUE-273: every leaked draft names this NPC


class _GeneratedQuest:
    """One quest this repetition generated, and how far it got through the lifecycle."""

    def __init__(self, quest_id: str, description: str) -> None:
        self.quest_id = quest_id
        self.description = description
        self.offered = False
        self.accepted = False
        self.completed = False


class QuestProbe:
    """Generates quests for a fresh giver, drives lifecycle transitions, measures rates."""

    engine_name = "quest"

    def __init__(self) -> None:
        """Start with no fixture; setup() seeds a fresh giver+player per repetition."""
        self._giver_id: str = ""
        self._player_id: str = ""
        self._quests: list[_GeneratedQuest] = []
        self._leak_baseline: int = 0
        self.invariants = {
            "no_leak_during_this_run": self._invariant_no_leak_during_this_run,
            "slot_fills_reference_real_nodes": self._invariant_slots_reference_real_nodes,
        }

    def _invariant_no_leak_during_this_run(self, client: httpx.Client) -> bool:
        """The background leak's target NPC gains no new drafts during this repetition."""
        return _draft_count(client, _BACKGROUND_LEAK_GIVER_ID) <= self._leak_baseline

    def _invariant_slots_reference_real_nodes(self, client: httpx.Client) -> bool:
        """Every generated quest's target_id (when present) resolves to a real node."""
        return all(_target_resolves(client, q.quest_id) for q in self._quests)

    def setup(self, client: httpx.Client) -> None:
        """Seed a fresh quest-giver Character and player; snapshot the leak baseline."""
        suffix = uuid.uuid4().hex[:8]
        self._giver_id, self._player_id = f"npc_probe_quest_{suffix}", f"player_probe_quest_{suffix}"
        client.post(f"{GRAPH_PREFIX}/nodes/Character", json={"properties": {
            "id": self._giver_id, "name": "Probe Quest Giver", "archetype": "commoner",
            "biography": "eval fixture", "is_player": False, "is_active": True,
            "created_at": now_iso(), "updated_at": now_iso(), "last_graph_updated_at": now_iso(),
            "gossipy": 50, "credulity": 50, "honesty": 50,
        }})
        self._quests = []
        self._leak_baseline = _draft_count(client, _BACKGROUND_LEAK_GIVER_ID)

    def drive(self, client: httpx.Client, ticks: int) -> None:
        """Generate `ticks` quests for the fresh giver, then offer/accept/evaluate each."""
        for _ in range(max(ticks, 1)):
            resp = client.post(f"{ADMIN_PREFIX}/quests/generate", json={"quest_giver_id": self._giver_id})
            if not is_ok(resp):
                continue
            data = resp.json().get("data", {})
            quest = _GeneratedQuest(data.get("quest_id", ""), data.get("description", ""))
            if quest.quest_id:
                self._drive_lifecycle(client, quest)
                self._quests.append(quest)

    def _drive_lifecycle(self, client: httpx.Client, quest: _GeneratedQuest) -> None:
        """Attempt offer -> accept -> evaluate for one generated quest."""
        offer = client.post(f"{ADMIN_PREFIX}/quests/{quest.quest_id}/offer")
        quest.offered = is_ok(offer)
        if quest.offered:
            accept = client.post("/v1/quest/accept", json={"quest_id": quest.quest_id, "player_id": self._player_id})
            quest.accepted = is_ok(accept)
        if quest.accepted:
            client.post("/v1/quest/evaluate", json={"quest_id": quest.quest_id, "player_id": self._player_id})
            final = client.get(f"{ADMIN_PREFIX}/quests/{quest.quest_id}")
            if is_ok(final):
                quest.completed = final.json().get("data", {}).get("quest", {}).get("status") == "completed"

    def measure(self, client: httpx.Client) -> dict[str, float]:
        """Report conversion rates, slot-validity, referential grounding, and leak delta."""
        if not self._quests:
            return {"background_draft_leak_delta": float(_draft_count(client, _BACKGROUND_LEAK_GIVER_ID) - self._leak_baseline)}
        generated = len(self._quests)
        offered = sum(1 for q in self._quests if q.offered)
        accepted = sum(1 for q in self._quests if q.accepted)
        metrics = {
            "quests_per_tick": 1.0,
            "offer_rate": offered / generated,
            "accept_rate": (accepted / offered) if offered else 0.0,
            "complete_rate": (sum(1 for q in self._quests if q.completed) / accepted) if accepted else 0.0,
            "slot_validity_rate": _slot_validity_rate(client, self._quests),
            "referential_grounding_rate": _referential_grounding_rate(client, self._quests),
            "background_draft_leak_delta": float(_draft_count(client, _BACKGROUND_LEAK_GIVER_ID) - self._leak_baseline),
        }
        return metrics


def _draft_count(client: httpx.Client, quest_giver_id: str) -> int:
    """Read GET /v1/admin/quests/drafts?quest_giver_id=... 's count, or 0 on failure."""
    resp = client.get(f"{ADMIN_PREFIX}/quests/drafts", params={"quest_giver_id": quest_giver_id})
    if not is_ok(resp):
        return 0
    count = resp.json().get("data", {}).get("count", 0)
    return int(count) if isinstance(count, int) else 0


def _quest_target_id(client: httpx.Client, quest_id: str) -> str | None:
    """Read a generated quest's target_id property, or None if absent/unreadable."""
    resp = client.get(f"{ADMIN_PREFIX}/quests/{quest_id}")
    if not is_ok(resp):
        return None
    target_id = resp.json().get("data", {}).get("quest", {}).get("target_id")
    return target_id if isinstance(target_id, str) and target_id else None


def _target_resolves(client: httpx.Client, quest_id: str) -> bool:
    """A quest with no target_id trivially satisfies the invariant; one with a target_id
    must resolve against at least one plausible node type."""
    target_id = _quest_target_id(client, quest_id)
    if target_id is None:
        return True
    return any(is_ok(client.get(f"{GRAPH_PREFIX}/nodes/{t}/{target_id}")) for t in _PLAUSIBLE_TARGET_TYPES)


def _slot_validity_rate(client: httpx.Client, quests: list[_GeneratedQuest]) -> float:
    """Fraction of quests carrying a target_id whose target_id resolves. Excludes quests
    with no target_id from the denominator — they have no slot fill to validate."""
    with_target = [q for q in quests if _quest_target_id(client, q.quest_id) is not None]
    if not with_target:
        return 0.0
    valid = sum(1 for q in with_target if _target_resolves(client, q.quest_id))
    return valid / len(with_target)


def _referential_grounding_rate(client: httpx.Client, quests: list[_GeneratedQuest]) -> float:
    """1 - mean(unsupported_entity_rate) over every quest's description text."""
    described = [q.description for q in quests if q.description]
    if not described:
        return 0.0
    vocabulary = fetch_vocabulary(client, base_url="", gen_dir=None)
    aliases = load_aliases(_ALIASES_PATH)
    rates = [unsupported_entity_rate(text, vocabulary, aliases).rate for text in described]
    return 1.0 - float(sum(rates) / len(rates))


def _make_quest_probe(client: httpx.Client) -> EngineProbe:
    """ProbeFactory: build a fresh QuestProbe (client unused — probe holds no client)."""
    del client
    return QuestProbe()


QUEST_PROBE_FACTORIES: dict[str, QuestProbeFactory] = {"quest": _make_quest_probe}
