"""
Module: test_pillars
Layer: demo_game (tests)
Purpose: Fixture-based unit tests for demo_game.runners.pillars.  Each test loads a
         JSONL transcript fixture and asserts the expected pillar verdict.  No I/O,
         no stack required.
Dependencies: demo_game.runners.pillars, json, pathlib
Used by: make test-demo
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo_game.runners.pillars import (
    PILLAR_DETERMINISM,
    PILLAR_FEEL,
    PILLAR_GOSSIP,
    PILLAR_REMEMBER,
    PILLAR_WORLD,
    check_determinism,
    check_feel,
    check_gossip,
    check_remember,
    check_world,
    judge_pillars,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> list[dict]:
    """Parse a JSONL fixture into a list of entry dicts."""
    path = _FIXTURES / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Red fixture — each LLM-sensitive pillar fails, WORLD NPC is at wrong location
# ---------------------------------------------------------------------------

class TestRedFixture:
    def test_feel_is_red(self) -> None:
        """Neutral emotion on all 3 reads → FEEL red."""
        ok, evidence = check_feel(_load("red_facts.jsonl"))
        assert not ok, f"expected FEEL red but got green: {evidence}"

    def test_remember_is_red(self) -> None:
        """Zero interaction_count and no memory_id → REMEMBER red."""
        ok, evidence = check_remember(_load("red_facts.jsonl"))
        assert not ok, f"expected REMEMBER red but got green: {evidence}"

    def test_gossip_is_red(self) -> None:
        """distortion_level=0 on all 3 reads → GOSSIP red."""
        ok, evidence = check_gossip(_load("red_facts.jsonl"))
        assert not ok, f"expected GOSSIP red but got green: {evidence}"

    def test_world_is_red(self) -> None:
        """At least one NPC at wrong location → WORLD red."""
        ok, evidence = check_world(_load("red_facts.jsonl"))
        assert not ok, f"expected WORLD red but got green: {evidence}"


# ---------------------------------------------------------------------------
# Green fixture — all pillars pass
# ---------------------------------------------------------------------------

class TestGreenFixture:
    def test_all_pillars_green(self) -> None:
        """Hand-crafted green transcript → every pillar is green."""
        entries = _load("green_facts.jsonl")
        verdicts = judge_pillars(entries, sha="testsha")
        red = [f"{v.pillar}: {v.evidence}" for v in verdicts if v.verdict != "green"]
        assert not red, f"expected all green, got red pillars: {red}"

    def test_sha_propagates_to_all_verdicts(self) -> None:
        """sha= kwarg is stored on every verdict."""
        entries = _load("green_facts.jsonl")
        verdicts = judge_pillars(entries, sha="deadbeef")
        assert all(v.sha == "deadbeef" for v in verdicts)

    def test_five_verdicts_returned(self) -> None:
        """judge_pillars returns exactly one verdict per pillar."""
        entries = _load("green_facts.jsonl")
        verdicts = judge_pillars(entries, sha="")
        pillars = {v.pillar for v in verdicts}
        assert pillars == {PILLAR_FEEL, PILLAR_REMEMBER, PILLAR_GOSSIP, PILLAR_WORLD, PILLAR_DETERMINISM}


# ---------------------------------------------------------------------------
# DETERMINISM: {} == {} is vacuously true — the check must catch empty seeds
# ---------------------------------------------------------------------------

class TestDeterminismEmptySeeds:
    def test_empty_seeds_yield_determinism_red(self) -> None:
        """{} == {} must return DETERMINISM red, not a vacuous green."""
        entries = [
            {
                "method": "POST",
                "path": "/v1/admin/batch/gossip_tick",
                "status": 200,
                "body": {"data": {"seeds_used": {}}},
            },
            {
                "method": "POST",
                "path": "/v1/admin/batch/gossip_tick",
                "status": 200,
                "body": {"data": {"seeds_used": {}}},
            },
        ]
        ok, evidence = check_determinism(entries)
        assert not ok
        assert "empty" in evidence.lower()

    def test_non_empty_matching_seeds_yield_green(self) -> None:
        """Two matching non-empty seeds_used dicts → DETERMINISM green."""
        seeds = {"captain_sorn:mira_innkeeper": 42}
        entries = [
            {"method": "POST", "path": "/v1/admin/batch/gossip_tick", "status": 200,
             "body": {"data": {"seeds_used": seeds}}},
            {"method": "POST", "path": "/v1/admin/batch/gossip_tick", "status": 200,
             "body": {"data": {"seeds_used": seeds}}},
        ]
        ok, evidence = check_determinism(entries)
        assert ok, evidence

    def test_differing_seeds_yield_red(self) -> None:
        """Two different non-empty seeds_used dicts → DETERMINISM red."""
        entries = [
            {"method": "POST", "path": "/v1/admin/batch/gossip_tick", "status": 200,
             "body": {"data": {"seeds_used": {"a:b": 1}}}},
            {"method": "POST", "path": "/v1/admin/batch/gossip_tick", "status": 200,
             "body": {"data": {"seeds_used": {"a:b": 2}}}},
        ]
        ok, evidence = check_determinism(entries)
        assert not ok, evidence
