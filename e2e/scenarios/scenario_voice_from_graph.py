"""
Module: scenario_voice_from_graph
Layer: e2e
Purpose: Verify that voice_descriptor stored on Character nodes in the graph shapes NPC dialogue.
         R1.4 moved voice from npc_voices.yaml to the graph — this test proves the graph field
         is actually read and influences LLM responses.
Dependencies: e2e.scenarios.conftest, e2e.helpers.llm_judge
Used by: make eval-llm-demo, pytest --scenarios-only -m llm_eval

Requirements:
  - Running NPC Engine API (docker-compose up -d)
  - Demo world seeded: make demo-seed
  - Ollama running with JUDGE_MODEL pulled
  - captain_sorn voice_descriptor: clipped military diction, direct, duty-focused
  - mira_innkeeper voice_descriptor: warm, observant, tavern gossip
"""

from __future__ import annotations

import uuid

import pytest

from e2e.helpers.judge_client import make_judge, ollama_reachable, resolve_judge_model
from e2e.scenarios.conftest import api_post

# Resolved judge model (mixtral:8x7b by default, DEC-143) — used in skip messages
# and the reachability probe. Previously this module hardcoded a qwen2.5:14b default
# and built its own adapter, bypassing the judge != generation-model collision guard
# entirely; routing through judge_client restores the invariant (DEC-149).
_JUDGE_MODEL = resolve_judge_model()


def _make_judge():
    """Create an OllamaAdapter for LLM judging with the separation invariant applied."""
    return make_judge()


def _ollama_reachable() -> bool:
    """Return True if Ollama is running AND the resolved judge model is pulled."""
    return ollama_reachable(_JUDGE_MODEL)


# ══════════════════════════════════════════════════════════════════════════════
# Test 1 — captain_sorn: voice_descriptor produces military diction
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_captain_sorn_voice_from_graph(
    http_client: httpx.Client,
) -> None:
    """captain_sorn's voice_descriptor (military/direct) shapes dialogue — sourced from graph."""
    if not _ollama_reachable():
        pytest.skip(
            f"Ollama not running or model {_JUDGE_MODEL!r} not pulled — "
            f"run: ollama serve && ollama pull {_JUDGE_MODEL}"
        )

    judge = _make_judge()

    dialogue_result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_demo",
            "npc_id": "captain_sorn",
            "player_message": "What's on your mind today?",
            "session_id": f"voice_sorn_{uuid.uuid4().hex[:8]}",
        },
    )
    assert dialogue_result["status"] == 200, (
        f"Dialogue failed: {dialogue_result}. "
        "Ensure demo world is seeded: make demo-seed"
    )
    npc_response = dialogue_result["body"].get("npc_response", "")
    assert npc_response, "Empty NPC response — check that the LLM stack is running."
    print(f"\n[captain_sorn voice]\n  {npc_response}\n")

    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=npc_response,
        criteria=(
            "Does this response have a military or command tone? "
            "YES if it is terse, declarative, references duty/order/watch/discipline, "
            "and avoids warmth or elaboration. "
            "NO if it is chatty, warm, or uses civilian/casual framing."
        ),
        llm_client=judge,
    )
    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"captain_sorn voice check FAILED — expected military/direct tone from graph voice_descriptor.\n"
        f"Response: {npc_response!r}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 2 — mira_innkeeper: voice_descriptor produces warm observant tone
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_mira_innkeeper_voice_from_graph(
    http_client: httpx.Client,
) -> None:
    """mira_innkeeper's voice_descriptor (warm, observant, gossip) shapes dialogue — sourced from graph."""
    if not _ollama_reachable():
        pytest.skip(
            f"Ollama not running or model {_JUDGE_MODEL!r} not pulled — "
            f"run: ollama serve && ollama pull {_JUDGE_MODEL}"
        )

    judge = _make_judge()

    dialogue_result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_demo",
            "npc_id": "mira_innkeeper",
            "player_message": "What's on your mind today?",
            "session_id": f"voice_mira_{uuid.uuid4().hex[:8]}",
        },
    )
    assert dialogue_result["status"] == 200, (
        f"Dialogue failed: {dialogue_result}. "
        "Ensure demo world is seeded: make demo-seed"
    )
    npc_response = dialogue_result["body"].get("npc_response", "")
    assert npc_response, "Empty NPC response — check that the LLM stack is running."
    print(f"\n[mira_innkeeper voice]\n  {npc_response}\n")

    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=npc_response,
        criteria=(
            "Does this response have a warm, conversational innkeeper tone? "
            "YES if it is personable, mentions guests/the inn/what she's noticed, "
            "or uses casual welcoming language. "
            "NO if it is terse, military, or purely transactional with no warmth."
        ),
        llm_client=judge,
    )
    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"mira_innkeeper voice check FAILED — expected warm/observant tone from graph voice_descriptor.\n"
        f"Response: {npc_response!r}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )
