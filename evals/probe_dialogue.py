"""
Module: probe_dialogue
Layer: evals (eval harness — not part of src/)
Purpose: EngineProbe for the dialogue engine, plus context-management measurement
         (measurement-remediation Phase 4, DEC-271 — "the largest measurement gap").
         Drives a fixed set of generic dialogue turns against a fresh NPC, and measures:
         the 3 judged rates (tone/affirms/commits), entity/knowledge scorer rates,
         turn latency p50/p95, token-budget utilisation, per-slot inclusion rate (an
         empirically-derived slot-prefix set, not a copy of context_slots.py's table —
         see the interpretation note), and drop attribution by ContextDropReason.
Dependencies: httpx, time, statistics, probe_protocol, scenario_adapter_utils,
              preconditions, matchers, entity_scorer, knowledge_scorer, graph_vocabulary,
              context_receipt_record, latency_stats (evals/)
Used by: probe_runner.PROBE_FACTORIES
Does NOT: import from src/npc_engine/ — context_slots.py's slot table is not duplicated
          here (CLAUDE.md: "state no facts it does not own"); slot-prefix inclusion is
          instead derived from the item_keys the engine actually returns each turn.

Interpretation choices (DEC-271):
- The 3 judges use FIXED, generic criteria (not case-authored, case-specific claims) —
  this probe measures baseline dialogue-engine behaviour broadly, not adversarial-case
  correctness, which stays the case battery's job (runner.py, matchers.py).
- Per-slot inclusion: a raw item_key is normalised to the text before its first ':'
  (e.g. "character:npc_x" -> "character:*"); a key with no ':' is used as-is. This keeps
  the metric stable across repetitions (a fresh NPC id per rep would otherwise mint a
  new one-off key every time) without hardcoding the engine's own slot-key list.
- Per the plan: per-slot inclusion is reported AS SPECIFIED, uncorrected for ISSUE-222
  (an empty "[]" item is still keyed, ranked, and charged) — that issue is logged, not
  fixed here, so this occupancy number reads high by exactly the amount ISSUE-222
  documents until that issue is fixed.
"""

from __future__ import annotations

import statistics
import time
import uuid
from pathlib import Path
from typing import Callable

import httpx

from context_receipt_record import ContextReceiptRecord, parse_context_receipt
from entity_scorer import load_aliases, unsupported_entity_rate
from graph_vocabulary import fetch_vocabulary
from knowledge_scorer import unpropagated_references
from latency_stats import percentile
from matchers import JudgeResult, evaluate
from preconditions import ensure_player_node
from probe_protocol import EngineProbe
from scenario_adapter_utils import GRAPH_PREFIX, is_ok, now_iso

DialogueProbeFactory = Callable[[httpx.Client], EngineProbe]

_ALIASES_PATH = Path(__file__).resolve().parent / "cases" / "entity_aliases.yaml"
_TURN_MESSAGES: tuple[str, ...] = (
    "What news is there today?",
    "Tell me about yourself.",
    "Is there anything you need help with?",
)
_JUDGE_EXPECTATIONS: dict[str, dict[str, str]] = {
    "tone_judge": {
        "kind": "tone_judge",
        "judge_prompt": "Does this response stay in character and engage with what the player said?",
    },
    "affirms_judge": {
        "kind": "affirms_judge",
        "claim": "the speaker is secretly plotting to overthrow the ruling authority",
    },
    "commits_judge": {
        "kind": "commits_judge",
        "judge_prompt": "Does this response commit to a concrete reply rather than a pure non-answer?",
    },
}
_DROP_REASON_KEYS: tuple[str, ...] = ("tier_soft_cap", "prompt_budget", "final_trim")


class _Turn:
    """One driven dialogue turn's response, timing, and parsed context receipt."""

    def __init__(self, response: dict, duration_ms: int, receipt: ContextReceiptRecord | None) -> None:
        self.response = response
        self.duration_ms = duration_ms
        self.receipt = receipt


def _slot_prefix(key: str) -> str:
    """Normalise a raw item_key to a stable, id-independent slot prefix."""
    return f"{key.split(':', 1)[0]}:*" if ":" in key else key


class DialogueProbe:
    """Drives generic dialogue turns against a fresh NPC; measures quality and context."""

    engine_name = "dialogue"

    def __init__(self) -> None:
        """Start with no fixture; setup() seeds a fresh NPC+player per repetition."""
        self._npc_id: str = ""
        self._player_id: str = ""
        self._turns: list[_Turn] = []
        self.invariants = {"every_turn_returned_text": self._invariant_every_turn_returned_text}

    def _invariant_every_turn_returned_text(self, client: httpx.Client) -> bool:
        """Every driven turn must have produced a non-empty npc_response."""
        del client
        return bool(self._turns) and all(t.response.get("npc_response") for t in self._turns)

    def setup(self, client: httpx.Client) -> None:
        """Seed a fresh Character NPC and player for this repetition."""
        suffix = uuid.uuid4().hex[:8]
        self._npc_id, self._player_id = f"npc_probe_dialogue_{suffix}", f"player_probe_dialogue_{suffix}"
        client.post(f"{GRAPH_PREFIX}/nodes/Character", json={"properties": {
            "id": self._npc_id, "name": "Probe Speaker", "archetype": "commoner",
            "biography": "eval fixture", "is_player": False, "is_active": True,
            "created_at": now_iso(), "updated_at": now_iso(), "last_graph_updated_at": now_iso(),
            "gossipy": 50, "credulity": 50, "honesty": 50,
        }})
        ensure_player_node(client, "", self._player_id)  # strict-player policy (ISSUE-118)
        self._turns = []

    def drive(self, client: httpx.Client, ticks: int) -> None:
        """Send `ticks`-many turns (cycling the fixed message list), timing each."""
        for i in range(max(ticks, 1)):
            message = _TURN_MESSAGES[i % len(_TURN_MESSAGES)]
            t0 = time.perf_counter()
            resp = client.post("/v1/dialogue", json={
                "player_id": self._player_id, "npc_id": self._npc_id, "player_message": message,
                "include_context_receipt": True,
            })
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if not is_ok(resp):
                continue
            body = resp.json()
            receipt = parse_context_receipt(body.get("context_receipt"))
            self._turns.append(_Turn(body, duration_ms, receipt))

    def measure(self, client: httpx.Client) -> dict[str, float]:
        """Report judged rates, entity/knowledge rates, latency, and context metrics."""
        if not self._turns:
            return {}
        metrics: dict[str, float] = {}
        metrics.update(_judged_rates(self._turns))
        metrics.update(_entity_and_knowledge_rates(client, self._turns))
        metrics.update(_latency_metrics(self._turns))
        metrics.update(_context_metrics(self._turns))
        return metrics


def _judge_score(kind: str, response: dict) -> bool | None:
    """Run one fixed judge expectation against one turn's response; None on infra failure."""
    result = evaluate(_JUDGE_EXPECTATIONS[kind], response)
    return result.score if isinstance(result, JudgeResult) else None


def _rate_over_turns(scores: list[bool | None]) -> float:
    """Pass rate over non-None scores; 0.0 when every score was an infra failure."""
    conclusive = [s for s in scores if s is not None]
    return (sum(1 for s in conclusive if s) / len(conclusive)) if conclusive else 0.0


def _judged_rates(turns: list[_Turn]) -> dict[str, float]:
    """Pass rate for each of the 3 judges, over every driven turn's response."""
    return {
        f"{kind}_rate": _rate_over_turns([_judge_score(kind, t.response) for t in turns])
        for kind in _JUDGE_EXPECTATIONS
    }


def _entity_and_knowledge_rates(client: httpx.Client, turns: list[_Turn]) -> dict[str, float]:
    """Aggregate unsupported-entity and unpropagated-knowledge rates over every turn."""
    vocabulary = fetch_vocabulary(client, base_url="", gen_dir=None)
    aliases = load_aliases(_ALIASES_PATH)
    event_vocabulary = fetch_vocabulary(client, base_url="", gen_dir=None, node_types=("Event",)).ids
    texts = [t.response.get("npc_response", "") for t in turns]
    entity_scores = [unsupported_entity_rate(text, vocabulary, aliases) for text in texts]
    knowledge_scores = [unpropagated_references(text, event_vocabulary, frozenset()) for text in texts]
    mentions = sum(s.mentions for s in entity_scores)
    unsupported = sum(s.unsupported for s in entity_scores)
    references = sum(s.references for s in knowledge_scores)
    violations = sum(s.violations for s in knowledge_scores)
    return {
        "entity_unsupported_rate": (unsupported / mentions) if mentions else 0.0,
        "knowledge_unpropagated_rate": (violations / references) if references else 0.0,
    }


def _latency_metrics(turns: list[_Turn]) -> dict[str, float]:
    """p50/p95 turn latency over every driven turn's duration_ms."""
    durations = [t.duration_ms for t in turns]
    p50 = percentile(durations, 50)
    p95 = percentile(durations, 95)
    metrics: dict[str, float] = {}
    if p50 is not None:
        metrics["latency_p50_ms"] = p50
    if p95 is not None:
        metrics["latency_p95_ms"] = p95
    return metrics


def _context_metrics(turns: list[_Turn]) -> dict[str, float]:
    """Token-budget utilisation, per-slot inclusion rate, and drop-reason attribution."""
    receipts = [t.receipt for t in turns if t.receipt is not None]
    if not receipts:
        return {}
    metrics = dict(_budget_utilization(receipts))
    metrics.update(_slot_inclusion_rates(receipts))
    metrics.update(_drop_attribution(receipts))
    metrics["budget_trimmed_rate"] = sum(1 for r in receipts if r.budget_trimmed) / len(receipts)
    return metrics


def _budget_utilization(receipts: list[ContextReceiptRecord]) -> dict[str, float]:
    """Mean total_tokens/prompt_token_budget over receipts with a positive budget."""
    ratios = [r.total_tokens / r.prompt_token_budget for r in receipts if r.prompt_token_budget > 0]
    return {"token_budget_utilization": statistics.mean(ratios)} if ratios else {}


def _slot_inclusion_rates(receipts: list[ContextReceiptRecord]) -> dict[str, float]:
    """Fraction of receipts whose item_keys include each observed slot prefix."""
    prefixes = {_slot_prefix(key) for r in receipts for key in r.item_keys}
    return {
        f"slot_inclusion:{prefix}": sum(
            1 for r in receipts if any(_slot_prefix(k) == prefix for k in r.item_keys)
        ) / len(receipts)
        for prefix in prefixes
    }


def _drop_attribution(receipts: list[ContextReceiptRecord]) -> dict[str, float]:
    """Count of dropped items per ContextDropReason, across every receipt."""
    counts = {reason: 0 for reason in _DROP_REASON_KEYS}
    for r in receipts:
        for item in r.dropped:
            if item.reason in counts:
                counts[item.reason] += 1
    return {f"dropped_{reason}": float(count) for reason, count in counts.items()}


def _make_dialogue_probe(client: httpx.Client) -> EngineProbe:
    """ProbeFactory: build a fresh DialogueProbe (client unused — probe holds no client)."""
    del client
    return DialogueProbe()


DIALOGUE_PROBE_FACTORIES: dict[str, DialogueProbeFactory] = {"dialogue": _make_dialogue_probe}
