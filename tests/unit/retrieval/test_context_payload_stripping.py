"""
test_context_payload_stripping.py - NON_PROMPT_NODE_FIELDS must hold at every assembly site.

`context_utils.NON_PROMPT_NODE_FIELDS` documents itself as the enforcement point for
CLAUDE.md's "Idempotent assembly" rule and says to apply it to *every* payload serialized
into prompt content. Only `_character_item` and the tier-0 items ever did. Graph readers
return `properties(n)` wholesale, so every unstripped site paid for a 384-float `embedding`
vector in prompt tokens and injected wall-clock timestamps that made the prompt differ
between two runs of the same turn (EVAL-P20.0 / DEC-176).

Measured live 2026-08-26: `location:loc_tavern` serialized at 2,188 tokens against a
1,312-token prompt budget, and `relation:player` at ~505, of which a `delta_log` of
per-tick audit records was ~420.

Does NOT: execute I/O, touch the graph, or call LLM services.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from npc_engine.retrieval.context.context_builder import (
    _build_tier_a_extended,
    _build_tier_b_c_items,
)
from npc_engine.retrieval.context.context_merger import ContextItem
from npc_engine.retrieval.context.context_utils import (
    NON_PROMPT_NODE_FIELDS,
    estimate_tokens,
)
from npc_engine.retrieval.graph_rag.subgraph_retriever import assemble_tier_a_context

# A payload big enough that failing to strip it is unmissable, and shaped like the real one.
_FAKE_EMBEDDING = [0.01 * i for i in range(384)]

_TIER_A_TOKEN_CEILING = 200
"""Well under the 721-token tier-A soft cap at the shipped 8192-token window.

A single tier-A item larger than this cannot coexist with the NPC's own beliefs, goals and
memories, which is the whole failure ISSUE-163 and ISSUE-199 describe.
"""


def _graph_noise() -> dict[str, Any]:
    """Every bookkeeping field a Neo4j `properties(n)` call drags into a payload."""
    return {
        "embedding": _FAKE_EMBEDDING,
        "created_at": "2026-08-26T10:00:00+00:00",
        "updated_at": "2026-08-26T10:00:00+00:00",
        "last_updated_at": "2026-08-26T10:00:00+00:00",
        "last_graph_updated_at": "2026-08-26T10:00:00+00:00",
        "last_embedding_indexed_at": "2026-08-26T10:00:00+00:00",
        "emotion_updated_at_tick": 3742,
        "schema_version": 3,
        "is_active": True,
        "is_player": False,
    }


def _character_payload() -> dict[str, Any]:
    return {"id": "mira_innkeeper", "name": "Mira", "archetype": "innkeeper", **_graph_noise()}


def _location_context() -> dict[str, Any]:
    return {
        "location": {
            "id": "loc_tavern",
            "name": "The Rusty Flagon",
            "descriptor": "A low-beamed common room.",
            "region": "riverlands",
            "location_tag": "tavern",
            **_graph_noise(),
        },
        "present_npcs": [{"id": "lira_fence", "name": "Lira", "archetype": "fence",
                          "faction": "thieves_guild", **_graph_noise()}],
    }


def _relation_bundle() -> dict[str, Any]:
    """A character bundle whose player relation carries the real 1,680-char delta_log."""
    delta_log = json.dumps([
        {"tick_id": 3244 + i, "cause_id": "dialogue:player_1:mira_innkeeper",
         "deltas": {"trust": 0, "fear": 0, "affection": 0},
         "timestamp": f"2026-08-26T10:3{i}:56.326037+00:00"}
        for i in range(6)
    ])
    return {
        "character": _character_payload(),
        "relations": [{
            "character": {"id": "player_1", "is_player": True},
            "relation": {"trust": 10, "fear": 0, "affection": 5, "interaction_count": 6,
                         "relevance_score": 0.0, "delta_log": delta_log,
                         "last_updated_at": "2026-08-26T11:00:26.624000+00:00"},
        }],
    }


def _all_tier_a_items() -> list[ContextItem]:
    """Every tier-A item the two assembly functions can produce, from noisy source data."""
    noisy_record = dict(_graph_noise())
    base = assemble_tier_a_context(
        npc_id="mira_innkeeper",
        character_bundle=_relation_bundle(),
        events=[{"event": {"id": "evt_1", "summary": "A fire in the market", "severity": 40,
                           **_graph_noise()},
                 "knowledge_state": "firsthand", "distorted_summary": None}],
        location_id="loc_tavern",
        location_context=_location_context(),
        group_memberships=[{"name": "Tavern Guild", "kind": "guild", "cohesion": 50,
                            "role": "member", **_graph_noise()}],
        believed_rumors=[{"content": "The war nears", "confidence": 70,
                          "mutation_distance": 1, **_graph_noise()}],
        traits=[{"name": "observant", "intensity": 80, "is_secret": False, **_graph_noise()}],
        active_pledges=[{"pledgee_id": "aldric_merchant", "pledgee_name": "Aldric",
                         "pledge_type": "debt", "severity": 60, **_graph_noise()}],
    )
    extended = _build_tier_a_extended(
        "player_1",
        [{"standing": 30, "faction": "neutral", **noisy_record}],
        {"id": "q1", "title": "Find the ledger", **noisy_record},
        {"trust": 10, "fear": 0, "delta_log": "[]", **noisy_record},
        [{"content": "A stranger paid in old coin", "emotional_charge": -60, **noisy_record}],
        [{"content": "The war will come", "confidence": 70, **noisy_record}],
        [{"objective": "Keep the peace", "urgency": 60, **noisy_record}],
        [{"name": "brass key", **noisy_record}],
        [{"content": "Lira fences stolen goods", "severity": 80, **noisy_record}],
        [{"description": "Owes Aldric coin", **noisy_record}],
        [{"summary": "A caravan was robbed", **noisy_record}],
        _Settings(),
        "mira_innkeeper",
        None,
    )
    return [*base, *extended]


class _Settings:
    """Minimal stand-in for the one Settings field _build_tier_a_extended reads."""

    MAX_SECOND_HOP_EVENTS = 3


def _offending_keys(value: Any) -> set[str]:
    """Return every NON_PROMPT_NODE_FIELDS key present at any depth of a parsed payload."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in NON_PROMPT_NODE_FIELDS:
                found.add(key)
            found |= _offending_keys(nested)
    elif isinstance(value, list):
        for entry in value:
            found |= _offending_keys(entry)
    return found


# ── the one test that guards the site somebody adds next year ────────────────


def test_every_assembled_tier_a_item_is_free_of_non_prompt_fields() -> None:
    """Six assembly sites, one assertion. Red today at `location:`, `relation:` and events."""
    offenders: dict[str, set[str]] = {}
    for item in _all_tier_a_items():
        bad = _offending_keys(json.loads(item.text))
        if bad:
            offenders[item.key] = bad
    assert offenders == {}


def test_no_assembled_tier_a_item_carries_an_embedding_vector() -> None:
    """The blunt form of the above: the substring must not survive anywhere."""
    carrying = [item.key for item in _all_tier_a_items() if "embedding" in item.text]
    assert carrying == []


def test_tier_b_and_c_rag_payloads_are_stripped() -> None:
    """The C7 prerequisite for turning RAG on: an unstripped rag: item is ~2,000 tokens."""
    rows = [
        {"id": f"node_{i}", "score": 0.9 - i * 0.1,
         "payload": {"content": "A rumour about the war", **_graph_noise()}}
        for i in range(4)
    ]
    tier_b, tier_c, _scores = _build_tier_b_c_items(rows)
    assert tier_b and tier_c, "fixture must populate both tiers for this to mean anything"
    for item in [*tier_b, *tier_c]:
        assert _offending_keys(json.loads(item.text)) == set(), item.key


# ── the two items ISSUE-199 measured ─────────────────────────────────────────


def test_the_location_item_fits_the_tier_a_budget() -> None:
    """Measured live at 2,188 tokens against a 1,312-token TOTAL prompt budget."""
    location = next(
        item for item in _all_tier_a_items() if item.key.startswith("location:")
    )
    assert estimate_tokens(location.text) < _TIER_A_TOKEN_CEILING


def test_the_relation_item_does_not_carry_the_delta_log() -> None:
    """~420 of the item's ~505 tokens were an audit trail of all-zero deltas.

    It is machine bookkeeping the mutation layer reads for rolling-window bounds, its
    entries carry wall-clock timestamps that change every turn, and the values it logs
    are already present as the edge's own trust/fear/affection.
    """
    relation = next(item for item in _all_tier_a_items() if item.key == "relation:player")
    payload = json.loads(relation.text)
    assert "delta_log" not in payload
    assert estimate_tokens(relation.text) < _TIER_A_TOKEN_CEILING
    # The fields that DO carry dialogue signal must survive the strip.
    assert payload["trust"] == 10
    assert payload["interaction_count"] == 6


@pytest.mark.parametrize("key_prefix", ["event:", "second_hop:"])
def test_event_items_strip_graph_bookkeeping_as_well_as_low_value_fields(key_prefix: str) -> None:
    """Events were given _LOW_VALUE_FIELDS only, so `embedding` and `created_at` survived."""
    items = [i for i in _all_tier_a_items() if i.key.startswith(key_prefix)]
    assert items, f"fixture must produce a {key_prefix} item"
    for item in items:
        assert _offending_keys(json.loads(item.text)) == set(), item.key
