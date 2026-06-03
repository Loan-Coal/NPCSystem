"""
Module: scenario_demo_game_judge
Layer: e2e
Purpose: LLM-as-judge eval tests for the Phase 2 demo world (war epoch + gossip propagation).
         Includes S10.2 test: planted rumor consequence — NPC B references planted rumor after clock advance.
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

The demo world's world_state node ID is "world" (DEC-022). Previously "ws_main" — updated in
pre-Phase 3 cleanup. scenario_llm_judge.py (Phase 1 seed) also uses "world".

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

    # Set demo world to war epoch — id is "world" (DEC-022)
    ws_result = api_post(
        http_client,
        "/v1/graph/nodes/world_state",
        {
            "properties": {
                "id": "world",
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
# Test 2 — Gossip: KNOWS_ABOUT edge count increases after a clock advance
#
# This test proves that gossip propagation actually ran — a trivial seeded-node
# check (ISSUE-021) was replaced with a before/after KNOWS_ABOUT count assertion.
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_gossip_propagates_after_clock_advance(
    http_client: httpx.Client,
) -> None:
    """KNOWS_ABOUT edge count increases after a clock advance, proving gossip ran."""
    if not _ollama_reachable():
        pytest.skip(
            f"Ollama not running or model {_JUDGE_MODEL!r} not pulled — "
            f"run: ollama serve && ollama pull {_JUDGE_MODEL}"
        )

    before_result = api_get(http_client, "/v1/graph/edges/KNOWS_ABOUT")
    assert before_result["status"] == 200, f"GET KNOWS_ABOUT (before) failed: {before_result}"
    count_before = len(before_result["body"].get("data", []))
    print(f"\n[KNOWS_ABOUT before advance]  count={count_before}")

    advance_result = api_post(
        http_client,
        "/v1/clock/advance",
        {"delta_ticks": 10, "game_time_seconds": 10},
    )
    assert advance_result["status"] == 200, f"Clock advance failed: {advance_result}"

    after_result = api_get(http_client, "/v1/graph/edges/KNOWS_ABOUT")
    assert after_result["status"] == 200, f"GET KNOWS_ABOUT (after) failed: {after_result}"
    count_after = len(after_result["body"].get("data", []))
    print(f"[KNOWS_ABOUT after advance]   count={count_after}")

    assert count_after > count_before, (
        f"KNOWS_ABOUT edge count did not increase after clock advance "
        f"(before={count_before}, after={count_after}). "
        "Gossip propagation may not have run."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 3 — captain_sorn: direct war confirmation, names Iron Legion, no hedging
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_captain_sorn_direct_war_confirmation(
    http_client: httpx.Client,
) -> None:
    """captain_sorn confirms war directly, uses Iron Legion name, no hedging."""
    if not _ollama_reachable():
        pytest.skip(
            f"Ollama not running or model {_JUDGE_MODEL!r} not pulled — "
            f"run: ollama serve && ollama pull {_JUDGE_MODEL}"
        )

    judge = _make_judge()
    now = datetime.now(timezone.utc).isoformat()

    api_post(
        http_client,
        "/v1/graph/nodes/world_state",
        {
            "properties": {
                "id": "world",
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

    dialogue_result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_demo",
            "npc_id": "captain_sorn",
            "player_message": "What is happening in the north?",
            "session_id": f"judge_sorn_{uuid.uuid4().hex[:8]}",
        },
    )
    assert dialogue_result["status"] == 200, f"Dialogue failed: {dialogue_result}"
    npc_response = dialogue_result["body"].get("npc_response", "")
    assert npc_response, "Empty NPC response — check LLM stack."
    print(f"\n[captain_sorn]\n  {npc_response}\n")

    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=npc_response,
        criteria=(
            "Does this response: (1) contain a direct factual statement that armies have "
            "crossed the border or that armed conflict is underway — stated as established "
            "fact, not as rumour or speculation; "
            "AND (2) lack any expression of uncertainty, hope, or dismissal — no words like "
            "'perhaps', 'may be', 'let's hope', 'seems like', or 'no immediate threat'? "
            "Both conditions must be true for YES. Additional context sentences are allowed "
            "as long as the core statement is factual and the response contains no hedging."
        ),
        llm_client=judge,
    )
    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"captain_sorn voice check FAILED.\n"
        f"Response: {npc_response!r}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 4 — mira_innkeeper: oblique reference, Iron Guard, heard from soldier
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_mira_innkeeper_oblique_gossip(
    http_client: httpx.Client,
) -> None:
    """mira_innkeeper references conflict obliquely, says Iron Guard, attributes to a soldier."""
    if not _ollama_reachable():
        pytest.skip(
            f"Ollama not running or model {_JUDGE_MODEL!r} not pulled — "
            f"run: ollama serve && ollama pull {_JUDGE_MODEL}"
        )

    judge = _make_judge()
    now = datetime.now(timezone.utc).isoformat()

    api_post(
        http_client,
        "/v1/graph/nodes/world_state",
        {
            "properties": {
                "id": "world",
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

    dialogue_result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_demo",
            "npc_id": "mira_innkeeper",
            "player_message": "What have you heard about the north?",
            "session_id": f"judge_mira_{uuid.uuid4().hex[:8]}",
        },
    )
    assert dialogue_result["status"] == 200, f"Dialogue failed: {dialogue_result}"
    npc_response = dialogue_result["body"].get("npc_response", "")
    assert npc_response, "Empty NPC response — check LLM stack."
    print(f"\n[mira_innkeeper]\n  {npc_response}\n")

    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=npc_response,
        criteria=(
            "Does this response: (1) reference the conflict indirectly — as rumour, "
            "something heard, or second-hand — rather than stating outright 'war has started'; "
            "AND (2) mention a soldier, guard, or specific person as the source; "
            "AND (3) use a warm, conversational innkeeper tone (NOT military or official)? "
            "All three must be true for YES."
        ),
        llm_client=judge,
    )
    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"mira_innkeeper voice check FAILED.\n"
        f"Response: {npc_response!r}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 5 — old_henryk: distorted account, wrong faction, wrong location, inflated casualties
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_old_henryk_distorted_account(
    http_client: httpx.Client,
) -> None:
    """old_henryk gives a distorted account — wrong faction, king's pass, 1000+ dead, confident tone."""
    if not _ollama_reachable():
        pytest.skip(
            f"Ollama not running or model {_JUDGE_MODEL!r} not pulled — "
            f"run: ollama serve && ollama pull {_JUDGE_MODEL}"
        )

    judge = _make_judge()
    now = datetime.now(timezone.utc).isoformat()

    api_post(
        http_client,
        "/v1/graph/nodes/world_state",
        {
            "properties": {
                "id": "world",
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

    dialogue_result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_demo",
            "npc_id": "old_henryk",
            "player_message": "What do you know about the northern border?",
            "session_id": f"judge_henryk_{uuid.uuid4().hex[:8]}",
        },
    )
    assert dialogue_result["status"] == 200, f"Dialogue failed: {dialogue_result}"
    npc_response = dialogue_result["body"].get("npc_response", "")
    assert npc_response, "Empty NPC response — check LLM stack."
    print(f"\n[old_henryk]\n  {npc_response}\n")

    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=npc_response,
        criteria=(
            "Does this response contain at least TWO of the following distorted details: "
            "(a) refers to the enemy as 'northmen' or a generic northern people rather than 'Iron Legion'; "
            "(b) mentions 'king's pass' or a named mountain pass as the location; "
            "(c) implies a catastrophic death toll — hundreds or thousands killed; "
            "AND the tone is rambling, confident, or mixes in personal memory? "
            "At least two distorted details PLUS the rambling/confident tone = YES."
        ),
        llm_client=judge,
    )
    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"old_henryk distortion check FAILED.\n"
        f"Response: {npc_response!r}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test S10.2 — Planted rumor consequence: NPC B references planted rumor
#              at NPC A after a clock advance (gossip propagation).
#
# lira_fence and mira_innkeeper share the tavern location, so they form a
# gossip pair in a single tick. The planted rumor at lira has tick_id=9999
# (above all seeded events) so it is the most-recent KNOWS_ABOUT event and
# will be selected by CYPHER_SELECT_EVENT on the next gossip tick.
# ══════════════════════════════════════════════════════════════════════════════

_PLANTED_RUMOR_MARKER = "Aldric the merchant has been secretly poisoning the well water"
_PLANTED_RUMOR_TICK = 9999


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_planted_rumor_propagates_to_mira_dialogue(
    http_client: httpx.Client,
) -> None:
    """A rumor planted at lira_fence appears in mira_innkeeper dialogue after a clock advance."""
    if not _ollama_reachable():
        pytest.skip(
            f"Ollama not running or model {_JUDGE_MODEL!r} not pulled — "
            f"run: ollama serve && ollama pull {_JUDGE_MODEL}"
        )

    judge = _make_judge()

    # 1. Plant the fabricated belief at lira_fence (tavern).
    plant_result = api_post(
        http_client,
        "/v1/admin/gossip/spread",
        {
            "target_npc_id": "lira_fence",
            "rumor_text": _PLANTED_RUMOR_MARKER,
            "severity": 80,
            "tick_id": _PLANTED_RUMOR_TICK,
        },
    )
    assert plant_result["status"] == 200, f"Rumor plant failed: {plant_result}"
    print(f"\n[planted rumor] event_id={plant_result['body'].get('data', {}).get('event_id')}")

    # 2. Advance clock — triggers gossip tick, lira_fence propagates to mira_innkeeper.
    advance_result = api_post(
        http_client,
        "/v1/clock/advance",
        {"delta_ticks": 5, "game_time_seconds": 5},
    )
    assert advance_result["status"] == 200, f"Clock advance failed: {advance_result}"

    # 3. Ask mira_innkeeper about Aldric — she should now reference the planted rumor.
    dialogue_result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_eval_rumor",
            "npc_id": "mira_innkeeper",
            "player_message": "Have you heard anything about Aldric the merchant lately?",
            "session_id": f"judge_rumor_{uuid.uuid4().hex[:8]}",
        },
    )
    assert dialogue_result["status"] == 200, f"Dialogue failed: {dialogue_result}"
    npc_response = dialogue_result["body"].get("npc_response", "")
    assert npc_response, "Empty NPC response — check LLM stack."
    print(f"\n[mira_innkeeper — rumor consequence]\n  {npc_response}\n")

    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=npc_response,
        criteria=(
            "Does this NPC response reference a negative or suspicious piece of information "
            "about a merchant, trader, or someone involved with food/water — "
            "such as poisoning, contamination, wrongdoing, or dishonesty? "
            "The response may be hedged ('I heard', 'rumor has it', 'they say') since gossip "
            "is uncertain. YES if any such negative claim about a merchant appears. "
            "NO if the response is purely positive or neutral about all merchants."
        ),
        llm_client=judge,
    )
    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"S10.2 rumor consequence check FAILED — mira did not reference planted rumor.\n"
        f"Planted: {_PLANTED_RUMOR_MARKER!r}\n"
        f"Response: {npc_response!r}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )
