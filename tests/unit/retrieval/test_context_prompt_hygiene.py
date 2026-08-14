"""
Module: test_context_prompt_hygiene
Layer: tests/unit
Purpose: Verify machine-only node properties never reach the LLM prompt (RET-P0.5).
         The 384-float `embedding` vector measured at 2,014 tokens — 3.9x the entire
         512-token prompt budget — inside a single pinned character profile.
Dependencies: subgraph_retriever, context_utils
Used by: pytest test runner
"""

from __future__ import annotations

import json

from npc_engine.retrieval.context.context_utils import (
    NON_PROMPT_NODE_FIELDS,
    estimate_tokens,
)
from npc_engine.retrieval.graph_rag.subgraph_retriever import assemble_tier_a_context

# Measured from the live stack on 2026-08-14 for mira_innkeeper.
MEASURED_EMBEDDING_TOKENS = 2014
PRODUCTION_PROMPT_BUDGET = 512


def _character_payload() -> dict[str, object]:
    """Return a character payload shaped like a real `properties(c)` row."""
    return {
        "id": "mira_innkeeper",
        "name": "Mira",
        "archetype": "innkeeper",
        "faction": "neutral",
        "biography": "Keeps the tavern and hears everything.",
        "voice_descriptor": "warm, wry, speaks in short sentences",
        "current_mood": "neutral",
        # Machine-only fields that must never be spent on prompt tokens.
        "embedding": [0.0123456789] * 384,
        "created_at": "2026-06-23T06:00:00Z",
        "updated_at": "2026-06-23T06:00:00Z",
        "last_graph_updated_at": "2026-06-23T06:00:00Z",
        "last_embedding_indexed_at": "2026-06-23T06:00:00Z",
        "is_active": True,
        "is_player": False,
    }


def _character_item_text(payload: dict[str, object]) -> str:
    """Return the serialized text of the pinned character context item."""
    items = assemble_tier_a_context(
        npc_id="mira_innkeeper",
        character_bundle={"character": payload, "relations": []},
        events=[],
        location_id=None,
        location_context=None,
    )
    character_items = [i for i in items if i.key.startswith("character:")]
    assert character_items, "expected a pinned character context item"
    return character_items[0].text


class TestEmbeddingNeverReachesThePrompt:
    """The embedding vector is machine state, not context."""

    def test_embedding_is_stripped_from_the_character_profile(self) -> None:
        """A 384-float vector must not be serialized into the prompt."""
        text = _character_item_text(_character_payload())

        assert "embedding" not in text
        assert "0.0123456789" not in text

    def test_character_profile_fits_a_sane_share_of_the_prompt_budget(self) -> None:
        """The pinned profile must not alone exceed the whole prompt budget."""
        tokens = estimate_tokens(_character_item_text(_character_payload()))

        assert tokens < PRODUCTION_PROMPT_BUDGET, (
            f"pinned character profile is {tokens} tokens against a "
            f"{PRODUCTION_PROMPT_BUDGET}-token budget"
        )

    def test_meaningful_profile_fields_are_preserved(self) -> None:
        """Stripping machine fields must not remove anything the NPC needs."""
        parsed = json.loads(_character_item_text(_character_payload()))

        assert parsed["name"] == "Mira"
        assert parsed["archetype"] == "innkeeper"
        assert parsed["biography"].startswith("Keeps the tavern")
        assert parsed["voice_descriptor"].startswith("warm, wry")


class TestBookkeepingFieldsAreStripped:
    """Timestamps and lifecycle flags carry no dialogue signal."""

    def test_bookkeeping_timestamps_are_stripped(self) -> None:
        """Graph bookkeeping timestamps must not consume prompt tokens."""
        text = _character_item_text(_character_payload())

        for field in ("created_at", "updated_at", "last_graph_updated_at", "last_embedding_indexed_at"):
            assert field not in text, f"{field} leaked into the prompt"

    def test_non_prompt_field_set_covers_the_measured_offenders(self) -> None:
        """The shared constant names every field measured leaking on 2026-08-14."""
        assert "embedding" in NON_PROMPT_NODE_FIELDS
        assert "last_embedding_indexed_at" in NON_PROMPT_NODE_FIELDS
        assert MEASURED_EMBEDDING_TOKENS > PRODUCTION_PROMPT_BUDGET
