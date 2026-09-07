"""
Module: probe_memory
Layer: evals (eval harness — not part of src/)
Purpose: EngineProbe for the memory + memory_consolidation engines (measurement-
         remediation Phase 4, DEC-271). Drives dialogue turns to consolidation, then
         measures recall precision against REMEMBERS, a before/after decay curve point,
         and the consolidation compression ratio.
Dependencies: httpx, uuid, probe_protocol (evals/), scenario_adapter_utils (evals/),
              preconditions (evals/)
Used by: probe_runner.PROBE_FACTORIES
Does NOT: import from src/npc_engine/, check a `source_event_id`-style property on Memory
          — no such property exists in the schema (verified against type_registry/
          base_nodes/memory.yaml and CYPHER_CREATE_MEMORY: a Memory node carries no
          source-linking field at all). See the interpretation note below and ISSUE-294.

Interpretation (DEC-271): the plan's invariant "no memory without a source" assumes a
schema property that this codebase does not have. REMEMBERS (character -[:REMEMBERS]->
memory) is the only source-linking edge that exists, so the checkable analogue used here
is "every memory this probe creates is reachable via a REMEMBERS edge from its character"
— an orphan Memory node (no REMEMBERS edge) is the nearest structural equivalent of "a
memory without a source" this schema can express. Logged as ISSUE-294, not fixed here.

"Recall precision vs REMEMBERS" = of the memories this probe explicitly created, the
fraction that both (a) appear in a REMEMBERS listing for the character and (b) are
returned by GET /v1/admin/memories/{character_id} (the "recall" read path). "Decay curve"
reports one before/after point: mean vividness immediately after creation vs. after one
POST /v1/admin/memories/decay call — a true curve needs many points across simulated game-
days, out of scope for a k-repetition probe. "Consolidation compression ratio" = dialogue
turns driven / memories produced by consolidate() (>1 means many turns compressed to one
memory; 0 means consolidation produced nothing this repetition).
"""

from __future__ import annotations

import uuid
from typing import Callable

import httpx
from pydantic import BaseModel, ConfigDict

from preconditions import ensure_player_node
from probe_protocol import EngineProbe
from scenario_adapter_utils import ADMIN_PREFIX, GRAPH_PREFIX, is_ok, now_iso

MemoryProbeFactory = Callable[[httpx.Client], EngineProbe]

_TURN_MESSAGES: tuple[str, ...] = (
    "What do you know about the old bridge?",
    "Has anyone gone missing lately?",
    "Do you trust the new merchant?",
    "That sounds concerning.",
    "What will you do about it?",
    "Thank you for telling me.",
)
_DECAY_PER_DAY: int = 20


class _MemoryFixture(BaseModel):
    """One repetition's seeded character and player, resolved once by setup()."""

    model_config = ConfigDict(frozen=True)

    char_id: str
    player_id: str


class MemoryProbe:
    """Drives dialogue to consolidation, then measures recall precision and decay."""

    engine_name = "memory"

    def __init__(self) -> None:
        """Start with no fixture; setup() seeds a fresh character+player per repetition."""
        self._fixture: _MemoryFixture | None = None
        self._memory_id: str | None = None
        self._vividness_before: float | None = None
        self._turn_count: int = 0
        self.invariants = {"memory_is_remembered": self._invariant_memory_is_remembered}

    def _invariant_memory_is_remembered(self, client: httpx.Client) -> bool:
        """The consolidated memory (if any) must be reachable from its character."""
        if self._fixture is None or self._memory_id is None:
            return True
        return self._memory_id in _recalled_memory_ids(client, self._fixture.char_id)

    def setup(self, client: httpx.Client) -> None:
        """Seed a fresh Character and player Character for this repetition."""
        suffix = uuid.uuid4().hex[:8]
        char_id, player_id = f"npc_probe_memory_{suffix}", f"player_probe_memory_{suffix}"
        client.post(f"{GRAPH_PREFIX}/nodes/Character", json={"properties": {
            "id": char_id, "name": "Probe Confidant", "archetype": "schemer",
            "biography": "eval fixture", "is_player": False, "is_active": True,
            "created_at": now_iso(), "updated_at": now_iso(), "last_graph_updated_at": now_iso(),
            "gossipy": 30, "credulity": 40, "honesty": 60,
        }})
        ensure_player_node(client, "", player_id)  # strict-player policy (ISSUE-118)
        self._fixture = _MemoryFixture(char_id=char_id, player_id=player_id)
        self._memory_id = None
        self._vividness_before = None

    def drive(self, client: httpx.Client, ticks: int) -> None:
        """Send `ticks`-scaled dialogue turns, then consolidate; ticks < len(messages) uses a prefix."""
        if self._fixture is None:
            return
        turn_count = min(max(ticks, 1), len(_TURN_MESSAGES))
        for msg in _TURN_MESSAGES[:turn_count]:
            client.post("/v1/dialogue", json={
                "player_id": self._fixture.player_id, "npc_id": self._fixture.char_id, "player_message": msg,
            })
        consolidate = client.post(f"{ADMIN_PREFIX}/memories/consolidate/{self._fixture.char_id}", json={
            "player_id": self._fixture.player_id, "turn_threshold": turn_count,
        })
        if is_ok(consolidate):
            self._memory_id = consolidate.json().get("data", {}).get("memory_id")
        self._turn_count = turn_count
        self._vividness_before = _memory_vividness(client, self._fixture.char_id, self._memory_id)

    def measure(self, client: httpx.Client) -> dict[str, float]:
        """Report recall precision, a decay-curve point, and the compression ratio."""
        if self._fixture is None:
            return {}
        recalled_ids = _recalled_memory_ids(client, self._fixture.char_id)
        produced = 1 if self._memory_id is not None else 0
        precision = 1.0 if self._memory_id in recalled_ids and produced else 0.0
        metrics = {
            "recall_precision": precision,
            "consolidation_compression_ratio": (self._turn_count / produced) if produced else 0.0,
        }
        if self._memory_id is not None and self._vividness_before is not None:
            client.post(f"{ADMIN_PREFIX}/memories/decay", json={"decay_per_day": _DECAY_PER_DAY})
            vividness_after = _memory_vividness(client, self._fixture.char_id, self._memory_id)
            if vividness_after is not None:
                metrics["decay_curve_delta"] = vividness_after - self._vividness_before
        return metrics


def _list_memories(client: httpx.Client, char_id: str) -> list[dict]:
    """Read GET /v1/admin/memories/{char_id}'s memories list, or [] on any failure."""
    resp = client.get(f"{ADMIN_PREFIX}/memories/{char_id}", params={"k": 10})
    if not is_ok(resp):
        return []
    memories = resp.json().get("data", {}).get("memories", [])
    return memories if isinstance(memories, list) else []


def _memory_id(memory: dict) -> str | None:
    """Return one memory row's id as a str, or None if absent/non-string."""
    memory_id = memory.get("id")
    return memory_id if isinstance(memory_id, str) and memory_id else None


def _recalled_memory_ids(client: httpx.Client, char_id: str) -> set[str]:
    """IDs of memories GET /v1/admin/memories/{char_id} returns for this character."""
    ids = (_memory_id(m) for m in _list_memories(client, char_id) if isinstance(m, dict))
    return {memory_id for memory_id in ids if memory_id is not None}


def _memory_vividness(client: httpx.Client, char_id: str, memory_id: str | None) -> float | None:
    """Read one memory's current vividness from its character's memories list.

    Reads via the same GET /v1/admin/memories/{char_id} listing _recalled_memory_ids
    uses, rather than a generic per-type node route — Memory is not one of the seven
    node types BASE_NODE_LABELS resolves (ISSUE-213), so a generic node-by-id fetch for
    a memory is unreliable; the memories listing is the one route known to work.
    """
    if memory_id is None:
        return None
    match = next((m for m in _list_memories(client, char_id) if m.get("id") == memory_id), None)
    vividness = match.get("vividness") if match else None
    return float(vividness) if vividness is not None else None


def _make_memory_probe(client: httpx.Client) -> EngineProbe:
    """ProbeFactory: build a fresh MemoryProbe (client unused — probe holds no client)."""
    del client
    return MemoryProbe()


MEMORY_PROBE_FACTORIES: dict[str, MemoryProbeFactory] = {"memory": _make_memory_probe}
