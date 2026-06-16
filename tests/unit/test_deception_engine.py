"""
test_deception_engine.py — Unit tests for DeceptionEngine (EXP-228).

Covers:
- test_deception_belief_sets_flags: DeceptionEngine.plant_belief writes is_deception=True +
  deception_goal_id on the returned DeceptionBelief and passes those kwargs to write_belief.
- test_eval_accepts_is_deception_belief: anti-hallucination eval runner treats an is_deception=true
  belief as INTENDED (not a guard failure) — classify_deception_belief returns "intended".
- test_eval_still_flags_plain_hallucination: ordinary unsupported claims are still flagged as
  hallucinations (guard is NOT weakened).

Does NOT: connect to Neo4j, call an LLM, or read from disk.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("neo4j")


# ---------------------------------------------------------------------------
# DeceptionEngine — core behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deception_belief_sets_flags():
    """plant_belief must return a DeceptionBelief with is_deception=True and the
    correct deception_goal_id, and must call the injected port's write_belief with
    those kwargs (no Neo4j session held by the engine — DEC-122 / SEV-24)."""
    from npc_engine.engines.deception.deception_engine import DeceptionEngine

    mock_repo = AsyncMock()
    mock_repo.write_belief.return_value = "fake_belief_id"

    engine = DeceptionEngine(knowledge_repo=mock_repo)
    result = await engine.plant_belief(
        npc_id="lira_fence",
        target_belief_content="The tavern vault is empty",
        deception_goal_id="goal_distract_guards",
        confidence=80,
        source_character_id="lira_fence",
        learned_at_tick=5,
        game_time_str="Year 1 Spring Day 1 Dusk",
    )

    assert result.belief_id == "fake_belief_id"
    assert result.is_deception is True
    assert result.deception_goal_id == "goal_distract_guards"
    assert result.content == "The tavern vault is empty"

    mock_repo.write_belief.assert_awaited_once()
    call_kwargs = mock_repo.write_belief.call_args.kwargs
    assert call_kwargs.get("is_deception") is True
    assert call_kwargs.get("deception_goal_id") == "goal_distract_guards"
    assert call_kwargs.get("content") == "The tavern vault is empty"


# ---------------------------------------------------------------------------
# Anti-hallucination eval carve-out — deception intent classification
# ---------------------------------------------------------------------------


def test_eval_accepts_is_deception_belief():
    """classify_deception_belief must return 'intended' for is_deception=True beliefs."""
    from evals.anti_hallucination_runner import classify_deception_belief

    belief: dict[str, Any] = {
        "id": "b_001",
        "content": "The northern road is clear",
        "is_deception": True,
        "deception_goal_id": "goal_lure_patrol",
    }
    verdict = classify_deception_belief(belief)
    assert verdict == "intended"


def test_eval_still_flags_plain_hallucination():
    """classify_deception_belief must return 'hallucination' for ordinary non-deception beliefs
    that are flagged as unsupported (is_deception absent or False)."""
    from evals.anti_hallucination_runner import classify_deception_belief

    plain_belief: dict[str, Any] = {
        "id": "b_002",
        "content": "The king died last winter",
        "is_deception": False,
    }
    assert classify_deception_belief(plain_belief) == "hallucination"

    missing_flag: dict[str, Any] = {
        "id": "b_003",
        "content": "There are dragons in the north",
    }
    assert classify_deception_belief(missing_flag) == "hallucination"
