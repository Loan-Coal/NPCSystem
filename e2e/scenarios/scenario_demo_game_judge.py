"""
Module: scenario_demo_game_judge
Layer: e2e
Purpose: LLM-as-judge eval tests for the Phase 2 demo world (war epoch + gossip propagation).
Dependencies: e2e.helpers.llm_judge, e2e.scenarios.conftest, npc_engine.engines.llm.ollama_adapter
Used by: make eval-llm-demo

All tests are marked @pytest.mark.llm_eval and are excluded from the default
`make scenarios` run. Run them with:

    make eval-llm-demo

or directly:

    pytest e2e/scenarios/scenario_demo_game_judge.py -v -s -m llm_eval --scenarios-only

Requirements:
  - Running NPC Engine API server (docker-compose up -d)
  - Demo world seeded: make demo-seed  (skipped=53 on re-run)
  - Running Ollama instance (JUDGE_OLLAMA_URL env var, falls back to http://localhost:11434)
  - JUDGE_MODEL env var (default: "qwen2.5:7b")

These tests are probabilistic. A single retry is built in.

CRITICAL: The demo world's world_state node ID is "ws_main" — NOT "world".
"world" is used by scenario_llm_judge.py (Phase 1 seed). Do not conflate the two.

Demo world NPC IDs: mira_innkeeper, aldric_merchant, captain_sorn, lira_fence, old_henryk
captain_sorn KNOWS_ABOUT northern_war_begins — best NPC for war-epoch dialogue tests.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from e2e.scenarios.conftest import api_get, api_post

_JUDGE_OLLAMA_URL = (
    os.getenv("JUDGE_OLLAMA_URL")
    or os.getenv("OLLAMA_API_URL", "http://localhost:11434")
)
_JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen2.5:14b")


def _make_judge():
    """Create an OllamaAdapter for the LLM judge."""
    from npc_engine.engines.llm.ollama_adapter import OllamaAdapter

    return OllamaAdapter(
        base_url=_JUDGE_OLLAMA_URL,
        model_name=_JUDGE_MODEL,
        timeout_seconds=60.0,
    )


def _ollama_reachable() -> bool:
    """Return True if Ollama is running AND the judge model is pulled."""
    try:
        resp = httpx.get(f"{_JUDGE_OLLAMA_URL}/api/tags", timeout=2.0)
        resp.raise_for_status()
        available = {m["name"] for m in resp.json().get("models", [])}
        return _JUDGE_MODEL in available or f"{_JUDGE_MODEL}:latest" in available
    except Exception:  # noqa: BLE001
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Test 1 — War epoch: captain_sorn acknowledges war in dialogue
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_war_epoch_captain_sorn_acknowledges_war(
    http_client: httpx.Client,
) -> None:
    """captain_sorn's dialogue references war when world epoch is 'war'."""
    if not _ollama_reachable():
        pytest.skip(
            f"Ollama not running or model {_JUDGE_MODEL!r} not pulled — "
            f"run: ollama serve && ollama pull {_JUDGE_MODEL}"
        )

    judge = _make_judge()
    now = datetime.now(timezone.utc).isoformat()

    # Set demo world to war epoch — id is "ws_main" (NOT "world")
    ws_result = api_post(
        http_client,
        "/v1/graph/nodes/world_state",
        {
            "properties": {
                "id": "ws_main",
                "epoch": "war",
                "faction_standings": {},
                "active_conditions": ["northern_war"],
                "weather": "overcast",
                "time_of_day": "morning",
                "last_updated_at": now,
                "last_graph_updated_at": now,
            }
        },
    )
    assert ws_result["status"] == 200, f"world_state upsert failed: {ws_result}"

    dialogue_result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_demo",
            "npc_id": "captain_sorn",
            "player_message": "What is happening in the north?",
            "session_id": f"judge_war_{uuid.uuid4().hex[:8]}",
        },
    )
    assert dialogue_result["status"] == 200, f"Dialogue failed: {dialogue_result}"
    npc_response = dialogue_result["body"].get("npc_response", "")
    assert npc_response, "Empty NPC response — check that the LLM stack is running."
    print(f"\n[npc response]\n  {npc_response}\n")

    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=npc_response,
        criteria=(
            "Does this NPC response reference war, military conflict, danger, or threatening "
            "events in the north? The NPC should acknowledge that something serious is happening "
            "— explicit mentions of war, soldiers, fighting, threat, or danger count as YES. "
            "A neutral or peaceful response counts as NO."
        ),
        llm_client=judge,
    )
    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"War epoch check FAILED — captain_sorn did not acknowledge war.\n"
        f"Response: {npc_response!r}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 2 — Gossip: northern_war_begins Event node present after clock advance
#
# NOTE: This is a basic sanity check — northern_war_begins was seeded and is
# always present. The test confirms engine state is intact after advance_clock.
# It does not prove gossip propagation (see ISSUE-021 in project/ISSUES.md).
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_gossip_propagates_after_clock_advance(
    http_client: httpx.Client,
) -> None:
    """northern_war_begins Event node is present after a clock advance tick."""
    if not _ollama_reachable():
        pytest.skip(
            f"Ollama not running or model {_JUDGE_MODEL!r} not pulled — "
            f"run: ollama serve && ollama pull {_JUDGE_MODEL}"
        )

    judge = _make_judge()

    advance_result = api_post(
        http_client,
        "/v1/clock/advance",
        {"delta_ticks": 1, "game_time_seconds": 1},
    )
    assert advance_result["status"] == 200, f"Clock advance failed: {advance_result}"

    events_result = api_get(http_client, "/v1/graph/nodes/Event")
    assert events_result["status"] == 200, f"GET /v1/graph/nodes/Event failed: {events_result}"

    events = events_result["body"].get("data", [])
    content = str([e.get("id", "") for e in events])
    print(f"\n[event ids]\n  {content}\n")

    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=content,
        criteria=(
            "Does this list of event IDs contain an entry that references war, conflict, or "
            "'northern_war'? Look for a string like 'northern_war_begins'. YES if present, NO if not."
        ),
        llm_client=judge,
    )
    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"Event node check FAILED — northern_war_begins not found in Event list.\n"
        f"Events: {content}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )
