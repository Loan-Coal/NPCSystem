"""
test_partial_cache_profile_isolation.py - one arm must not be served the other arm's data.

`PartialDialogueContextCache` keys the NPC-profile slot on `(npc_id,
npc_last_graph_updated_at)`. The value it caches is `_fetch_npc_profile_data(...)`, whose
`events` list is read with `limit=profile.events_limit` -- a RETRIEVAL PROFILE field. Neither
half of the key mentions the profile, so two turns for the same NPC at the same graph
timestamp collide, and the second one is served the first one's event list.

That is not a hypothetical. The cache is a process-wide singleton shared by the HTTP and
WebSocket paths, and `paired_arms` interleaves the arms within a single run --
rep -> case -> profile -- so the default arm's 5 events are served to the wide_events arm that
asked for 15, and the run records a profile it did not actually retrieve under.

**The ordering is the point.** With an empty vector store a contaminated cache has no
symptom, so this must be fixed BEFORE P8 populates the corpus. Afterwards, arm 2 inheriting
arm 1's event list reads as a plausible treatment effect and there is nothing in the
receipts that would say otherwise.

Does NOT: execute real Neo4j queries, or call an LLM.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.retrieval.dialogue_context.dialogue_context_cache import (
    PartialDialogueContextCache,
)

from .test_context_builder import (  # reuse the one harness that stubs the whole read set
    FakeEmbeddingIndex,
    _llm_config,
    _patch_graph_calls,
)
from npc_engine.config import Settings
from npc_engine.retrieval.context import ContextItem, build_serialized_context
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.schema.retrieval_profile_models import RetrievalProfile

_DEFAULT_EVENTS_LIMIT = 5
"""What `build_default_profile` derives for the default arm."""

_WIDE_EVENTS_LIMIT = 15
"""What the shipped `wide_events` arm asks for.

This WAS `wide_events` until P9 split the arm in two: `events_limit` feeds tier A and the
top-ks feed tiers B and C, so one arm may not move both. The cache-isolation defect this
module pins is unchanged — `events_limit` is still the profile field read inside the value
the profile cache stores, and `wide_events` is now the arm that varies it."""


def _settings() -> Settings:
    return Settings(NEO4J_PASSWORD="not_the_default_pw", RAG_TOP_K=5)


def _config_with_wide_events() -> LLMConfig:
    """The shipped `wide_events` arm, declared against the harness config.

    Its `events_limit` is the field that makes this a cache-isolation problem rather than a
    style question: it is read inside the value the profile cache stores.
    """
    base = _llm_config()
    return LLMConfig(**{**base.model_dump(), "retrieval_profiles": {
        "wide_events": RetrievalProfile(
            weight_profile=None, rag_top_k=15, graph_rag_top_k=15,
            events_limit=_WIDE_EVENTS_LIMIT, cross_encoder_enabled=False, skip_rag=False,
        ),
    }})


async def _build(
    monkeypatch, cache: PartialDialogueContextCache, seen: list[int] | None = None, **kwargs: Any
) -> str:
    """One turn against a shared cache, optionally recording the events limit asked for.

    The recorder is installed AFTER `_patch_graph_calls`, which stubs the whole read set --
    installing it first is silently overwritten and the test then asserts on an empty list.
    """
    _patch_graph_calls(
        monkeypatch,
        tier_a_items=[
            ContextItem(key="character:npc_1", text='{"id":"npc_1","name":"Aldric"}',
                        tier="tierA", priority=100),
        ],
    )
    if seen is not None:
        _record_events_limit(monkeypatch, seen)
    return await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=_settings(),
        llm_config=_config_with_wide_events(),
        embedding_index=FakeEmbeddingIndex(rows=[]),
        npc_id="npc_1",
        player_message="hello",
        session_turns=["player: hi"],
        context_cache=cache,
        **kwargs,
    )


def _record_events_limit(monkeypatch, seen: list[int]) -> None:
    """Stub `get_events_for_npc` so the test can see the limit it was actually asked for."""

    async def fake_events(session, *, npc_id, limit=5):
        seen.append(limit)
        return []

    monkeypatch.setattr(
        "npc_engine.retrieval.context.context_builder.get_events_for_npc", fake_events
    )


# ---------------------------------------------------------------------------
# The key itself
# ---------------------------------------------------------------------------


def test_two_profiles_do_not_share_a_profile_cache_key() -> None:
    """The value cached under this key depends on profile.events_limit."""
    cache = PartialDialogueContextCache(ttl_seconds=300)
    default = cache.build_profile_key(
        npc_id="npc_1", npc_last_graph_updated_at="t0", profile_name="default"
    )
    wide = cache.build_profile_key(
        npc_id="npc_1", npc_last_graph_updated_at="t0", profile_name="wide_events"
    )
    assert default != wide


def test_the_same_profile_twice_produces_the_same_key() -> None:
    """The guard against 'fixing' this by making the cache never hit."""
    cache = PartialDialogueContextCache(ttl_seconds=300)
    first = cache.build_profile_key(
        npc_id="npc_1", npc_last_graph_updated_at="t0", profile_name="wide_events"
    )
    second = cache.build_profile_key(
        npc_id="npc_1", npc_last_graph_updated_at="t0", profile_name="wide_events"
    )
    assert first == second


def test_the_beliefs_goals_key_deliberately_ignores_the_profile() -> None:
    """`_fetch_beliefs_goals_data` reads no profile field, so adding one would cost hit rate.

    Asserted rather than left implicit: an unnecessary key component is a cache-hit-rate
    regression that nothing else in the suite would notice.
    """
    cache = PartialDialogueContextCache(ttl_seconds=300)
    key = cache.build_beliefs_goals_key(npc_id="npc_1", npc_last_graph_updated_at="t0")
    assert "wide_events" not in key and "default" not in key


# ---------------------------------------------------------------------------
# The one that matters: what the reader is actually asked for
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_wide_events_turn_does_not_serve_the_default_arms_event_list(monkeypatch) -> None:
    """RED before the fix: the second build never reaches the reader at all.

    Two builds, one shared cache, two different arms. The reader must be asked TWICE, with
    5 and then 15 -- not once with 5 and then served from cache.
    """
    cache = PartialDialogueContextCache(ttl_seconds=300)
    seen: list[int] = []

    await _build(monkeypatch, cache, seen, retrieval_profile=None)
    await _build(monkeypatch, cache, seen, retrieval_profile="wide_events")

    assert seen == [_DEFAULT_EVENTS_LIMIT, _WIDE_EVENTS_LIMIT], (
        f"expected the reader to be asked for {_DEFAULT_EVENTS_LIMIT} then "
        f"{_WIDE_EVENTS_LIMIT} events, got {seen}"
    )


@pytest.mark.asyncio
async def test_the_same_profile_twice_still_hits_the_cache(monkeypatch) -> None:
    """The guard against fixing isolation by disabling the cache.

    Two identical turns must reach the reader ONCE. Without this, adding the profile to the
    key and adding a random nonce to the key are indistinguishable to the test suite.
    """
    cache = PartialDialogueContextCache(ttl_seconds=300)
    seen: list[int] = []

    await _build(monkeypatch, cache, seen, retrieval_profile="wide_events")
    await _build(monkeypatch, cache, seen, retrieval_profile="wide_events")

    assert seen == [_WIDE_EVENTS_LIMIT], (
        f"the second identical turn should have been a cache hit; reader saw {seen}"
    )


# ---------------------------------------------------------------------------
# The dead sub-cache
# ---------------------------------------------------------------------------


def test_the_world_sub_cache_is_gone() -> None:
    """Zero callers, and `size()` counted a dict nothing ever wrote to.

    Kept as a test rather than just deleted so the removal is deliberate: re-adding it
    without a caller should be a conscious act, not an accident.
    """
    cache = PartialDialogueContextCache(ttl_seconds=300)
    for name in ("build_world_key", "get_world", "set_world"):
        assert not hasattr(cache, name), f"{name} has no callers and should not exist"


def test_size_counts_only_sub_caches_that_are_written_to() -> None:
    """`size()` used to sum a third dict that was permanently empty."""
    cache = PartialDialogueContextCache(ttl_seconds=300)
    assert cache.size() == 0
    cache.set_profile(
        cache.build_profile_key(
            npc_id="npc_1", npc_last_graph_updated_at="t0", profile_name="default"
        ),
        "profile_value",
    )
    cache.set_beliefs_goals(
        cache.build_beliefs_goals_key(npc_id="npc_1", npc_last_graph_updated_at="t0"),
        "bg_value",
    )
    assert cache.size() == 2
