"""
Module: test_debug_retrieval_arm_parity
Layer: test (unit)
Purpose: Pin that GET /v1/admin/debug/retrieval assembles context the way a DIALOGUE
         TURN does — same player_id, same retrieval profile, same session turns, same
         cache — and that it reports the receipt rather than a reparsed skeleton.
Dependencies: pytest, unittest.mock; npc_engine.api.routes.admin.debug_retrieval
Used by: pytest (make test / make check); gate 4 of the P9 arm probe reads this route.

WHY THIS MODULE EXISTS
Every inner-life number in the P0-P8 headline was measured through this route, and the
route passed NO player_id, NO retrieval profile, NO session turns and NO cache. Three
consequences, all measured on the eval baseline at cc24c2b before this was fixed:

  * `get_reputation_context_for_npc` and CYPHER_PROPAGATED_REPUTATION_FOR_NPC both match
    against "", so `player_reputation`, `propagated_reputation` and `player_relation` are
    STRUCTURALLY invisible through the probe. The instrument could not observe DEC-206's
    own deliverable.
  * With no profile the route always assembled the default arm, so it could not observe an
    arm difference AT ALL — which is precisely what P9's gate 4 needs it to do.
  * It called the receipt-FREE `build_serialized_context` and reparsed the serialized JSON
    into top-level slot names, so it could report neither `item_keys` nor `tier_spend`.
    Measured: 11 slot names / 978 tokens through the route against 16 item keys / 1013
    tokens on the dialogue turn, same NPC and same message.

Does NOT: execute real Neo4j queries, call an LLM, or touch the vector store.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.api.routes.admin import debug_retrieval as route_module
from npc_engine.retrieval.context.context_receipt import ContextReceipt, TierSpend

_NPC = "captain_sorn"
_QUERY = "what news"
_PLAYER = "player_demo"
_ARM = "wide_rag"

_SERIALIZED = '{"world": {"day": 1}, "npc": {"beliefs": []}}'


def _receipt(profile: str = "default", tier_b_items: int = 2) -> ContextReceipt:
    """A receipt shaped like the ones the dialogue path publishes."""
    return ContextReceipt(
        retrieval_profile=profile,
        item_keys=("world", "beliefs", "rag:lira_fence"),
        tier_spend=(
            TierSpend(tier="tier0", items=1, tokens=93),
            TierSpend(tier="tierA", items=8, tokens=687),
            TierSpend(tier="tierB", items=tier_b_items, tokens=93),
            TierSpend(tier="tierC", items=3, tokens=140),
        ),
        total_tokens=1013,
        prompt_token_budget=25888,
    )


class _Recorder:
    """Stands in for build_serialized_context_with_receipt and records its kwargs."""

    def __init__(self, profile: str = "default") -> None:
        self.seen: dict[str, Any] = {}
        self._profile = profile

    async def __call__(self, **kwargs: Any) -> tuple[str, ContextReceipt]:
        self.seen = kwargs
        return _SERIALIZED, _receipt(self._profile)


class _MockSession:
    """Minimal stand-in for neo4j.AsyncSession — never called in unit scope."""


class _MockEmbeddingIndex:
    """Minimal stand-in for EmbeddingIndex — never called in unit scope."""


class _MockSettings:
    """Minimal Settings stand-in with the fields the route reads."""

    PROMPT_TOKEN_BUDGET: int = 25888
    RAG_TOP_K: int = 5


class _MockLLMConfig:
    """Minimal LLMConfig stand-in."""


class _MockCache:
    """Minimal PartialDialogueContextCache stand-in — identity is all that is asserted."""


async def _call(recorder: _Recorder, monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> Any:
    """Invoke the route handler with the recorder installed, filling unset params."""
    monkeypatch.setattr(
        route_module, "build_serialized_context_with_receipt", recorder
    )
    params: dict[str, Any] = {
        "npc_id": _NPC,
        "query": _QUERY,
        "session": _MockSession(),
        "embedding_index": _MockEmbeddingIndex(),
        "settings": _MockSettings(),
        "llm_config": _MockLLMConfig(),
        "context_cache": _MockCache(),
    }
    params.update(kwargs)
    return await route_module.get_debug_retrieval(**params)


# ---------------------------------------------------------------------------
# Parity with a dialogue turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_probe_forwards_the_player_id_it_was_given(monkeypatch) -> None:
    """Without this the probe matches every reputation query against "".

    This is a correctness dependency of the 8/8 inner-life headline, not a tidy-up: the
    three reputation slots cannot be observed through the probe at all until it holds a
    player id.
    """
    recorder = _Recorder()
    await _call(recorder, monkeypatch, player_id=_PLAYER)
    assert recorder.seen["player_id"] == _PLAYER


@pytest.mark.asyncio
async def test_the_probe_selects_the_arm_it_was_asked_for(monkeypatch) -> None:
    """Gate 4 diffs two arms' item_keys through this route. A route that always
    assembles the default arm makes that diff vacuously empty."""
    recorder = _Recorder(profile=_ARM)
    await _call(recorder, monkeypatch, retrieval_profile=_ARM)
    assert recorder.seen["retrieval_profile"] == _ARM


@pytest.mark.asyncio
async def test_the_probe_forwards_the_session_turns_it_was_given(monkeypatch) -> None:
    """A real turn carries conversation history; `expand_query` folds it into the RAG
    query, so a probe with an empty history retrieves against a different signal."""
    turns = ["player: hello", "npc: well met"]
    recorder = _Recorder()
    await _call(recorder, monkeypatch, session_turn=turns)
    assert list(recorder.seen["session_turns"]) == turns


@pytest.mark.asyncio
async def test_the_probe_defaults_to_no_session_turns(monkeypatch) -> None:
    """The pre-P9 behaviour stays the default, so every number measured through this
    route before P9 remains reproducible by omitting the new parameters."""
    recorder = _Recorder()
    await _call(recorder, monkeypatch)
    assert list(recorder.seen["session_turns"]) == []
    assert recorder.seen["player_id"] is None


@pytest.mark.asyncio
async def test_the_probe_bypasses_the_shared_cache_unless_asked(monkeypatch) -> None:
    """The context cache is a PROCESS-WIDE singleton and gate 4 sweeps arms back to back.

    P7 made the cache key carry the profile name, so a hit cannot cross arms any more —
    but a probe that shares the cache still measures a cache hit rather than an assembly
    on its second call, and a cache hit publishes NO receipt (DEC-195). Default off; the
    parameter exists so cache behaviour itself remains observable.
    """
    recorder = _Recorder()
    await _call(recorder, monkeypatch)
    assert recorder.seen["context_cache"] is None


@pytest.mark.asyncio
async def test_the_probe_uses_the_shared_cache_when_asked(monkeypatch) -> None:
    """The other half: a dialogue turn DOES use the cache, so parity must be reachable."""
    cache = _MockCache()
    recorder = _Recorder()
    await _call(recorder, monkeypatch, use_context_cache=True, context_cache=cache)
    assert recorder.seen["context_cache"] is cache


# ---------------------------------------------------------------------------
# The receipt is the payload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_probe_reports_the_receipt_not_a_reparsed_skeleton(monkeypatch) -> None:
    """`item_keys` and `tier_spend` are what gate 4 diffs. Reparsing the serialized JSON
    yields top-level slot names, which cannot distinguish two `rag:` hits from none."""
    recorder = _Recorder()
    response = await _call(recorder, monkeypatch)
    assert response.context_receipt is not None
    assert response.context_receipt.item_keys == ("world", "beliefs", "rag:lira_fence")
    spend = {row.tier: row.items for row in response.context_receipt.tier_spend}
    assert spend["tierB"] == 2


@pytest.mark.asyncio
async def test_the_probe_reports_the_resolved_arm_name(monkeypatch) -> None:
    """The arm's own claim about itself, echoed back so a recorded probe result is
    interpretable without the request that produced it (DEC-194)."""
    recorder = _Recorder(profile=_ARM)
    response = await _call(recorder, monkeypatch, retrieval_profile=_ARM)
    assert response.retrieval_profile == _ARM


@pytest.mark.asyncio
async def test_a_cached_turn_reports_no_receipt_rather_than_an_empty_one(monkeypatch) -> None:
    """DEC-195: an empty receipt reads as 'nothing reached the model', which is false.

    The legacy cache short-circuits assembly, so there is genuinely nothing to report.
    """

    async def cached(**_kwargs: Any) -> tuple[str, None]:
        return _SERIALIZED, None

    monkeypatch.setattr(route_module, "build_serialized_context_with_receipt", cached)
    response = await route_module.get_debug_retrieval(
        npc_id=_NPC,
        query=_QUERY,
        session=_MockSession(),  # type: ignore[arg-type]
        embedding_index=_MockEmbeddingIndex(),  # type: ignore[arg-type]
        settings=_MockSettings(),  # type: ignore[arg-type]
        llm_config=_MockLLMConfig(),  # type: ignore[arg-type]
        context_cache=_MockCache(),  # type: ignore[arg-type]
    )
    assert response.context_receipt is None
    assert response.context_items, "the serialized slots must still be reported"
