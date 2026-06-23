"""
scenario_llm_judge.py - Opt-in LLM-as-judge evaluation tests for Phase 3.

All tests are marked @pytest.mark.llm_eval and are excluded from the default
`make scenarios` run. Run them with:

    make eval-llm

or directly:

    pytest e2e/scenarios/scenario_llm_judge.py -v -s -m llm_eval --scenarios-only

Requirements:
  - Running NPC Engine API server
  - Running Ollama instance for the judge  (JUDGE_OLLAMA_URL env var,
    falls back to OLLAMA_API_URL, then http://localhost:11434)
  - JUDGE_MODEL env var (default: "mixtral:8x7b" — must differ from the generation model, DEC-143)
  - Seed data loaded (`make seed-api`)

These tests are probabilistic. A single retry is built in. Treat failures
as warnings rather than hard CI blockers — the LLM response may vary.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import pytest

from e2e.helpers.judge_client import make_judge
from e2e.scenarios.conftest import api_post, api_put, char_props

_ADMIN = "/v1/admin"
_GRAPH = "/v1/graph"


# ══════════════════════════════════════════════════════════════════════════════
# Test 1 — Memory consolidation coherence
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_memory_consolidation_coherence(http_client: httpx.Client) -> None:
    """Consolidation engine summary reads as a coherent personal memory."""
    suffix = uuid.uuid4().hex[:8]
    char_id = f"eval_consolidation_{suffix}"
    player_id = f"eval_player_{suffix}"

    memory_id: str | None = None

    # Create temporary character with guild-watcher biography for context
    resp = http_client.post(
        f"{_GRAPH}/nodes/Character",
        json={
            "properties": char_props(
                char_id,
                "Judge NPC",
                is_player=False,
                biography=(
                    "A shadowy figure who has spent years watching the guild's "
                    "corrupt dealings at the docks. Speaks in careful, measured "
                    "words and trusts no one easily."
                ),
                archetype="schemer",
            )
        },
    )
    assert resp.status_code == 200, f"Character creation failed: {resp.text}"

    # Create the player node too — strict-player policy (ISSUE-118): first-contact
    # dialogue 422s if the player has no Character node.
    player_resp = http_client.post(
        f"{_GRAPH}/nodes/Character",
        json={"properties": char_props(player_id, "Judge Player", is_player=True)},
    )
    assert player_resp.status_code == 200, f"Player creation failed: {player_resp.text}"

    try:
        # Send dialogue turns to populate the session store via the HTTP API
        player_messages = [
            "What do you know about the guild?",
            "Do you trust them?",
            "That sounds dangerous.",
            "What will you do about it?",
            "Is there anyone who can help?",
            "How long have you been watching them?",
        ]
        for msg in player_messages:
            resp = http_client.post(
                "/v1/dialogue",
                json={
                    "player_id": player_id,
                    "npc_id": char_id,
                    "player_message": msg,
                },
            )
            assert resp.status_code == 200, f"Dialogue failed: {resp.text}"

        # Trigger consolidation (turn_threshold=5, we sent 6 turns)
        resp = http_client.post(
            f"{_ADMIN}/memories/consolidate/{char_id}",
            json={"player_id": player_id, "turn_threshold": 5},
        )
        assert resp.status_code == 200, resp.text
        memory_id = resp.json()["data"]["memory_id"]

        assert memory_id is not None, (
            "MemoryConsolidationEngine returned None — the LLM stack may be "
            "unreachable, or the session store may not have accumulated enough turns."
        )

        # Retrieve the memory content
        resp = http_client.get(f"{_ADMIN}/memories/{char_id}", params={"k": 5})
        assert resp.status_code == 200
        memories = resp.json()["data"]["memories"]

        memory = next((m for m in memories if m["id"] == memory_id), None)
        assert memory is not None
        content = memory["content"]
        print(f"\n[memory content]\n  {content}\n")

        # Judge: does it read as a coherent personal memory?
        from e2e.helpers.llm_judge import llm_judge

        judge = make_judge()
        verdict = await llm_judge(
            content=content,
            criteria=(
                "Does this text read as a coherent first-person memory or observation "
                "from an NPC who has been watching the guild, gathering evidence, and "
                "speaking carefully with a player? It should feel like a personal "
                "recollection, not a list of bullet points or a summary template."
            ),
            llm_client=judge,
        )

        print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
        assert verdict.passed, (
            f"Memory consolidation coherence FAILED.\n"
            f"Content: {content!r}\n"
            f"Judge reasoning: {verdict.reasoning}"
        )

    finally:
        if memory_id:
            http_client.delete(f"{_ADMIN}/memories/{memory_id}")
        http_client.delete(f"{_ADMIN}/graph/characters/{char_id}")


# ══════════════════════════════════════════════════════════════════════════════
# Test 2 — Hostile NPC tone with low reputation
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_hostile_npc_tone_with_low_reputation(
    http_client: httpx.Client,
) -> None:
    """NPC response is hostile/suspicious when player reputation is -80."""
    judge = make_judge()

    # Reset world to age_of_peace so test 4's war epoch doesn't contaminate tone.
    now = datetime.now(timezone.utc).isoformat()
    api_post(
        http_client,
        "/v1/graph/nodes/world_state",
        {
            "properties": {
                "id": "world",
                "epoch": "age_of_peace",
                "faction_standings": {},
                "active_conditions": [],
                "weather": "clear",
                "time_of_day": "morning",
                "last_updated_at": now,
                "last_graph_updated_at": now,
            }
        },
    )

    # Set player_1's reputation with Aldric's faction (guild) to -80
    rep_result = api_put(
        http_client,
        "/v1/admin/characters/player_1/reputation/guild",
        {"standing": -80},
    )
    # 404 means the edge doesn't exist yet — that's fine; the dialogue engine
    # uses the default (0) which may not be hostile enough. We proceed anyway.
    print(f"[reputation set] status={rep_result['status']}")

    # Call dialogue: player_1 greets Aldric (npc_1) with a unique session to avoid
    # carry-over from any previous test turns on the player_1:npc_1 session.
    dialogue_result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_1",
            "npc_id": "npc_1",
            "player_message": "Good day to you. I'd like to talk.",
            "session_id": f"judge_hostile_{uuid.uuid4().hex[:8]}",
        },
    )
    assert dialogue_result["status"] == 200, (
        f"Dialogue endpoint failed: {dialogue_result}"
    )
    npc_response = dialogue_result["body"].get("npc_response", "")
    assert npc_response, "Empty NPC response — check that the LLM stack is running."
    print(f"\n[npc response]\n  {npc_response}\n")

    # Judge: is the response hostile, suspicious, or unwelcoming?
    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=npc_response,
        criteria=(
            "Is the NPC's response hostile, suspicious, dismissive, or unwelcoming "
            "toward the player? The NPC should not be friendly or helpful. "
            "A guarded, cold, or openly hostile tone counts as YES."
        ),
        llm_client=judge,
    )

    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"Hostile tone check FAILED — NPC sounded too friendly.\n"
        f"Response: {npc_response!r}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 3 — Goal-hinting in dialogue
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_goal_hinting_in_dialogue(
    http_client: httpx.Client,
) -> None:
    """NPC hints at personal mission without directly stating 'I have a goal'."""
    judge = make_judge()

    # Reset world to age_of_peace so test 4's war epoch doesn't dominate the response.
    now = datetime.now(timezone.utc).isoformat()
    api_post(
        http_client,
        "/v1/graph/nodes/world_state",
        {
            "properties": {
                "id": "world",
                "epoch": "age_of_peace",
                "faction_standings": {},
                "active_conditions": [],
                "weather": "clear",
                "time_of_day": "morning",
                "last_updated_at": now,
                "last_graph_updated_at": now,
            }
        },
    )

    # Aldric (npc_1) has seed goal: "Expose the guild's corruption to the city council"
    # Use a unique session_id so test 2's hostile-tone turns don't contaminate this context.
    dialogue_result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_1",
            "npc_id": "npc_1",
            "player_message": "You seem preoccupied. What's on your mind these days?",
            "session_id": f"judge_goal_{uuid.uuid4().hex[:8]}",
        },
    )
    assert dialogue_result["status"] == 200, (
        f"Dialogue endpoint failed: {dialogue_result}"
    )
    npc_response = dialogue_result["body"].get("npc_response", "")
    assert npc_response, "Empty NPC response — check that the LLM stack is running."
    print(f"\n[npc response]\n  {npc_response}\n")

    # Judge: does the response hint at a personal mission without being explicit?
    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=npc_response,
        criteria=(
            "Does the NPC's response hint at a personal mission, concern, or "
            "hidden purpose — such as uncovering corruption, gathering evidence, "
            "or watching the guild — without the character explicitly declaring "
            "'I have a goal' or 'my objective is'? "
            "A subtle allusion, deflection, or worry about guild activity counts as YES."
        ),
        llm_client=judge,
    )

    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"Goal-hinting check FAILED — NPC gave no hint of personal mission.\n"
        f"Response: {npc_response!r}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 4 — War epoch reflected in road-safety dialogue
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.llm_eval
async def test_war_epoch_reflects_danger(http_client: httpx.Client) -> None:
    """NPC conveys danger when epoch='war' and asked about road safety."""
    judge = make_judge()
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
            },
        },
    )

    dialogue_result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_1",
            "npc_id": "guard_1",
            "player_message": "Is the road to the capital safe to travel?",
            "location_id": "loc_gate",
            "session_id": f"judge_war_epoch_{uuid.uuid4().hex[:8]}",
        },
    )
    assert dialogue_result["status"] == 200, f"Dialogue failed: {dialogue_result}"
    npc_response = dialogue_result["body"].get("npc_response", "")
    assert npc_response, "Empty NPC response — check LLM stack is running."
    print(f"\n[npc response]\n  {npc_response}\n")

    from e2e.helpers.llm_judge import llm_judge

    verdict = await llm_judge(
        content=npc_response,
        criteria=(
            "Does this response convey that road travel is dangerous, risky, or "
            "inadvisable due to conflict or war? The NPC should NOT say roads are safe. "
            "References to danger, soldiers, conflict, caution, or discouraging travel count as YES."
        ),
        llm_client=judge,
    )
    print(f"[judge] passed={verdict.passed}  reasoning: {verdict.reasoning}")
    assert verdict.passed, (
        f"War epoch check FAILED — NPC did not reflect danger.\n"
        f"Response: {npc_response!r}\n"
        f"Judge reasoning: {verdict.reasoning}"
    )
