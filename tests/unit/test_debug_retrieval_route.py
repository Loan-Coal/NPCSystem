"""
Unit tests for the GET /admin/debug/retrieval route handler.

Tests patch build_serialized_context so no Neo4j or Ollama connection is needed.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.api.routes.debug_retrieval import get_debug_retrieval


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockSession:
    """Minimal stand-in for neo4j.AsyncSession — never called in unit scope."""


class _MockEmbeddingIndex:
    """Minimal stand-in for EmbeddingIndex — never called in unit scope."""


class _MockSettings:
    """Minimal Settings stand-in with fields consumed by the route."""

    PROMPT_TOKEN_BUDGET: int = 4096
    RAG_TOP_K: int = 5


class _MockLLMConfig:
    """Minimal LLMConfig stand-in."""


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

# build_serialized_context returns a compact prompt-ready JSON object.
# The debug route must parse it into a flat list of context items.
_CONTEXT_PAYLOAD = {
    "world": {"year": 1, "season": "spring"},
    "events": [{"id": "e1", "description": "The northern war has begun."}],
}
_CONTEXT_JSON = json.dumps(_CONTEXT_PAYLOAD)


@pytest.mark.asyncio
async def test_debug_retrieval_returns_context_items() -> None:
    """Happy path: patched build_serialized_context returns items in the response."""
    with patch(
        "npc_engine.api.routes.debug_retrieval.build_serialized_context",
        new_callable=AsyncMock,
        return_value=_CONTEXT_JSON,
    ):
        response = await get_debug_retrieval(
            npc_id="mira_innkeeper",
            query="war news",
            session=_MockSession(),  # type: ignore[arg-type]
            embedding_index=_MockEmbeddingIndex(),  # type: ignore[arg-type]
            settings=_MockSettings(),  # type: ignore[arg-type]
            llm_config=_MockLLMConfig(),  # type: ignore[arg-type]
        )

    assert response.npc_id == "mira_innkeeper"
    assert response.query == "war news"
    assert len(response.context_items) >= 1
    keys = {item.key for item in response.context_items}
    assert "world" in keys or "events" in keys


@pytest.mark.asyncio
async def test_debug_retrieval_total_tokens_is_non_negative() -> None:
    """total_tokens field must be a non-negative integer."""
    with patch(
        "npc_engine.api.routes.debug_retrieval.build_serialized_context",
        new_callable=AsyncMock,
        return_value=_CONTEXT_JSON,
    ):
        response = await get_debug_retrieval(
            npc_id="mira_innkeeper",
            query="war news",
            session=_MockSession(),  # type: ignore[arg-type]
            embedding_index=_MockEmbeddingIndex(),  # type: ignore[arg-type]
            settings=_MockSettings(),  # type: ignore[arg-type]
            llm_config=_MockLLMConfig(),  # type: ignore[arg-type]
        )

    assert isinstance(response.total_tokens, int)
    assert response.total_tokens >= 0


@pytest.mark.asyncio
async def test_debug_retrieval_empty_context() -> None:
    """When context JSON is an empty object the handler returns zero items."""
    with patch(
        "npc_engine.api.routes.debug_retrieval.build_serialized_context",
        new_callable=AsyncMock,
        return_value=json.dumps({}),
    ):
        response = await get_debug_retrieval(
            npc_id="old_henryk",
            query="plague",
            session=_MockSession(),  # type: ignore[arg-type]
            embedding_index=_MockEmbeddingIndex(),  # type: ignore[arg-type]
            settings=_MockSettings(),  # type: ignore[arg-type]
            llm_config=_MockLLMConfig(),  # type: ignore[arg-type]
        )

    assert response.context_items == []
    assert response.total_tokens >= 0
