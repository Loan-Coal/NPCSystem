"""
test_dialogue_archetype_fallback.py - Unit tests for archetype-keyed dialogue
fallbacks (ISSUE-081): the structured-output fallback and the canned/degradation
tier must use the NPC's real archetype line instead of the hardcoded "default".

Does NOT: hit Neo4j or a real LLM (adapter + session are mocked).
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from neo4j import AsyncSession

from npc_engine.engines.dialogue.llm_client import DialogueLLMClient
from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
from npc_engine.graph.graph_reader import get_npc_archetype

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FALLBACK_PATH = str(_REPO_ROOT / "src" / "npc_engine" / "data" / "fallback_responses.json")


def _make_client() -> DialogueLLMClient:
    return DialogueLLMClient(
        llm_client=MockLLMAdapter(),
        fallback_path=_FALLBACK_PATH,
        max_tokens=256,
        temperature=0.7,
        top_p=0.95,
        stop_sequences=[],
        log_prompts=False,
    )


def test_fallback_payload_uses_archetype_line() -> None:
    client = _make_client()
    payload = client.fallback_response_payload(archetype="guard")
    assert payload["npc_response"] == "Move along, citizen."


def test_fallback_payload_defaults_when_archetype_unknown() -> None:
    client = _make_client()
    payload = client.fallback_response_payload(archetype="nonexistent_archetype")
    assert payload["npc_response"] == "I need a moment to think."


def test_fallback_payload_defaults_when_no_archetype_given() -> None:
    client = _make_client()
    payload = client.fallback_response_payload()
    assert payload["npc_response"] == "I need a moment to think."


# ---------------------------------------------------------------------------
# get_npc_archetype graph reader
# ---------------------------------------------------------------------------


class _Result:
    def __init__(self, record: dict | None) -> None:
        self._record = record

    async def single(self) -> dict | None:
        return self._record

    async def consume(self) -> None:
        return None


class _Session:
    def __init__(self, record: dict | None) -> None:
        self._record = record
        self.run_args: tuple | None = None

    async def run(self, query: str, params: dict) -> _Result:
        self.run_args = (query, params)
        return _Result(self._record)


@pytest.mark.asyncio
async def test_get_npc_archetype_returns_field() -> None:
    session = _Session({"archetype": "innkeeper"})
    result = await get_npc_archetype(cast(AsyncSession, session), "mira_innkeeper")
    assert result == "innkeeper"


@pytest.mark.asyncio
async def test_get_npc_archetype_none_when_missing() -> None:
    session = _Session(None)
    result = await get_npc_archetype(cast(AsyncSession, session), "ghost")
    assert result is None
