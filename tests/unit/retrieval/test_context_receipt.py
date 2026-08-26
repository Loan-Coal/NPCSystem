"""
test_context_receipt.py - Unit tests for the assembled-context receipt (B).

Does NOT: execute real Neo4j queries or call an LLM.

Dependencies injected: Monkeypatched retrieval and world readers.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from npc_engine.config import Settings
from npc_engine.retrieval.context.context_merger import ContextItem, MergedContext
from npc_engine.retrieval.context.context_receipt import (
    ContextReceipt,
    DroppedItem,
    build_context_receipt,
)

from tests.unit.retrieval.test_context_builder import (
    FakeEmbeddingIndex,
    _llm_config,
    _patch_graph_calls,
)


def _item(key: str, tier: str, text: str = "x") -> ContextItem:
    return ContextItem(key=key, text=text, tier=tier, priority=10)  # type: ignore[arg-type]


def _dropped(key: str, tier: str, reason: str = "prompt_budget") -> DroppedItem:
    """One attributed drop, as fill_to_budget_with_report reports it.

    build_context_receipt takes the drops as data rather than deriving them from a
    pre/post set difference: only the enforcer knows which STAGE removed each item, and
    that is lost the moment it is recomputed from two contexts (P4 / ISSUE-197).
    """
    return DroppedItem(key=key, tier=tier, reason=reason)  # type: ignore[arg-type]


def _settings() -> Settings:
    return Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
        PROMPT_TOKEN_BUDGET=800,
    )


# ---------------------------------------------------------------------------
# The pure builder
# ---------------------------------------------------------------------------


def test_receipt_names_only_the_items_that_survived_the_budget() -> None:
    """The receipt is about what REACHED the model, not what the retriever ranked."""
    post = MergedContext(items=[_item("a", "tierA"), _item("b", "tierB")])

    receipt = build_context_receipt(
        profile_name="default", post_budget=post,
        dropped=(_dropped("c", "tierC"),), prompt_token_budget=800,
    )

    assert receipt.item_keys == ("a", "b")
    # dropped_keys is now computed from `dropped`, and must still read the same way for
    # evals/context_receipt_record.py and every transcript already on disk.
    assert receipt.dropped_keys == ("c",)
    assert receipt.budget_trimmed is True


def test_receipt_reports_no_trim_when_every_assembled_item_reached_the_model() -> None:
    """budget_trimmed False is a positive claim, not merely an empty dropped list."""
    post = MergedContext(items=[_item("a", "tierA")])

    receipt = build_context_receipt(
        profile_name="aggressive", post_budget=post, dropped=(), prompt_token_budget=800,
    )

    assert receipt.budget_trimmed is False
    assert receipt.dropped_keys == ()
    assert receipt.retrieval_profile == "aggressive"


def test_receipt_spends_tokens_per_tier_and_totals_them() -> None:
    """Per-tier spend is what distinguishes 'RAG was retrieved' from 'RAG got budget'."""
    post = MergedContext(items=[
        _item("a", "tierA", text="a" * 40),
        _item("b", "tierB", text="b" * 80),
    ])

    receipt = build_context_receipt(
        profile_name="default", post_budget=post, dropped=(), prompt_token_budget=800,
    )

    spend = {row.tier: row for row in receipt.tier_spend}
    assert spend["tierA"].items == 1
    assert spend["tierB"].items == 1
    assert spend["tierB"].tokens > spend["tierA"].tokens
    assert receipt.total_tokens == sum(row.tokens for row in receipt.tier_spend)
    assert receipt.prompt_token_budget == 800


def test_receipt_lists_every_tier_even_when_empty() -> None:
    """An absent tier must read as zero spend, not as an unreported tier."""
    receipt = build_context_receipt(
        profile_name="default",
        post_budget=MergedContext(items=[_item("a", "tierA")]),
        dropped=(),
        prompt_token_budget=800,
    )

    assert tuple(row.tier for row in receipt.tier_spend) == ("tier0", "tierA", "tierB", "tierC")


def test_receipt_is_frozen() -> None:
    """Receipts are evidence; they must not be editable after the fact."""
    receipt = build_context_receipt(
        profile_name="default",
        post_budget=MergedContext(items=[]),
        dropped=(),
        prompt_token_budget=800,
    )
    with pytest.raises(ValidationError):
        receipt.retrieval_profile = "tampered"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# The pipeline entry point
# ---------------------------------------------------------------------------


async def _build_with_receipt(monkeypatch, **kwargs):
    from npc_engine.retrieval.context.context_builder import build_serialized_context_with_receipt

    _patch_graph_calls(
        monkeypatch,
        tier_a_items=[
            ContextItem(key="character:npc_1", text='{"id":"npc_1","name":"Aldric"}',
                        tier="tierA", priority=100),
        ],
    )
    return await build_serialized_context_with_receipt(
        session=None,  # type: ignore[arg-type]
        settings=_settings(),
        llm_config=_llm_config(),
        embedding_index=FakeEmbeddingIndex(rows=[]),
        npc_id="npc_1",
        player_message="hello",
        session_turns=["player: hi"],
        **kwargs,
    )


@pytest.mark.asyncio
async def test_pipeline_returns_a_receipt_naming_the_resolved_profile(monkeypatch) -> None:
    """With no override the receipt must name the deployment default, not None."""
    _serialized, receipt = await _build_with_receipt(monkeypatch)

    assert isinstance(receipt, ContextReceipt)
    assert receipt.retrieval_profile == _settings().RETRIEVAL_PROFILE


@pytest.mark.asyncio
async def test_pipeline_receipt_keys_are_the_keys_that_reached_the_prompt(monkeypatch) -> None:
    """The character item is assembled, so it must appear in the receipt's key list."""
    _serialized, receipt = await _build_with_receipt(monkeypatch)

    assert receipt is not None
    assert "character:npc_1" in receipt.item_keys
    assert receipt.total_tokens > 0


@pytest.mark.asyncio
async def test_receipt_variant_serializes_identically_to_the_plain_builder(monkeypatch) -> None:
    """THE guard: asking for a receipt must not change one byte of assembled context."""
    from npc_engine.retrieval.context.context_builder import build_serialized_context

    with_receipt, _receipt = await _build_with_receipt(monkeypatch)

    _patch_graph_calls(
        monkeypatch,
        tier_a_items=[
            ContextItem(key="character:npc_1", text='{"id":"npc_1","name":"Aldric"}',
                        tier="tierA", priority=100),
        ],
    )
    plain = await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=_settings(),
        llm_config=_llm_config(),
        embedding_index=FakeEmbeddingIndex(rows=[]),
        npc_id="npc_1",
        player_message="hello",
        session_turns=["player: hi"],
    )

    assert with_receipt == plain


@pytest.mark.asyncio
async def test_pipeline_receipt_records_the_overridden_profile_name(monkeypatch) -> None:
    """An arm must be able to prove from the receipt which arm it was."""
    _serialized, receipt = await _build_with_receipt(monkeypatch, retrieval_profile="default")

    assert receipt is not None
    assert receipt.retrieval_profile == "default"


def test_dropped_keys_projects_every_attributed_drop_in_order() -> None:
    """dropped_keys is computed, so it cannot drift from `dropped` -- pin that it does not.

    The field it replaced was stored alongside the drops, which is exactly how two
    representations of the same fact fall out of step.
    """
    receipt = build_context_receipt(
        profile_name="default",
        post_budget=MergedContext(items=[_item("a", "tierA")]),
        dropped=(
            _dropped("memories", "tierA", "tier_soft_cap"),
            _dropped("rag:r1", "tierB", "prompt_budget"),
            _dropped("nearby_npcs", "tierA", "final_trim"),
        ),
        prompt_token_budget=800,
    )

    assert receipt.dropped_keys == ("memories", "rag:r1", "nearby_npcs")
    assert receipt.budget_trimmed is True
    assert [d.reason for d in receipt.dropped] == [
        "tier_soft_cap", "prompt_budget", "final_trim",
    ]


def test_dropped_keys_survives_a_serialization_round_trip() -> None:
    """It must stay in the JSON: evals/context_receipt_record.py reads it by that name."""
    receipt = build_context_receipt(
        profile_name="default",
        post_budget=MergedContext(items=[]),
        dropped=(_dropped("goals", "tierA"),),
        prompt_token_budget=800,
    )

    assert receipt.model_dump()["dropped_keys"] == ("goals",)
