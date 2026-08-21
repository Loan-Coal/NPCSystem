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
from npc_engine.retrieval.context.context_receipt import ContextReceipt, build_context_receipt

from tests.unit.retrieval.test_context_builder import (
    FakeEmbeddingIndex,
    _llm_config,
    _patch_graph_calls,
)


def _item(key: str, tier: str, text: str = "x") -> ContextItem:
    return ContextItem(key=key, text=text, tier=tier, priority=10)  # type: ignore[arg-type]


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
    pre = MergedContext(items=[_item("a", "tierA"), _item("b", "tierB"), _item("c", "tierC")])
    post = MergedContext(items=[_item("a", "tierA"), _item("b", "tierB")])

    receipt = build_context_receipt(
        profile_name="default", pre_budget=pre, post_budget=post, prompt_token_budget=800,
    )

    assert receipt.item_keys == ("a", "b")
    assert receipt.dropped_keys == ("c",)
    assert receipt.budget_trimmed is True


def test_receipt_reports_no_trim_when_every_assembled_item_reached_the_model() -> None:
    """budget_trimmed False is a positive claim, not merely an empty dropped list."""
    pre = MergedContext(items=[_item("a", "tierA")])

    receipt = build_context_receipt(
        profile_name="aggressive", pre_budget=pre, post_budget=pre, prompt_token_budget=800,
    )

    assert receipt.budget_trimmed is False
    assert receipt.dropped_keys == ()
    assert receipt.retrieval_profile == "aggressive"


def test_receipt_spends_tokens_per_tier_and_totals_them() -> None:
    """Per-tier spend is what distinguishes 'RAG was retrieved' from 'RAG got budget'."""
    pre = MergedContext(items=[
        _item("a", "tierA", text="a" * 40),
        _item("b", "tierB", text="b" * 80),
    ])

    receipt = build_context_receipt(
        profile_name="default", pre_budget=pre, post_budget=pre, prompt_token_budget=800,
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
        pre_budget=MergedContext(items=[_item("a", "tierA")]),
        post_budget=MergedContext(items=[_item("a", "tierA")]),
        prompt_token_budget=800,
    )

    assert tuple(row.tier for row in receipt.tier_spend) == ("tier0", "tierA", "tierB", "tierC")


def test_receipt_is_frozen() -> None:
    """Receipts are evidence; they must not be editable after the fact."""
    receipt = build_context_receipt(
        profile_name="default",
        pre_budget=MergedContext(items=[]),
        post_budget=MergedContext(items=[]),
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
