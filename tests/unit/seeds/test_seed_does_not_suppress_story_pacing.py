"""
Module: test_seed_does_not_suppress_story_pacing
Layer: tests/unit/seeds
Purpose: Guards that the demo seed does not hold story pacing in suppression for the
    whole demo, which silently blocks ACT 5's battle beat.

StoryPacingEngine suppresses (caps max_event_severity at suppression_event_severity_cap)
whenever any non-completed quest has severity >= high_severity_quest_threshold. The seed
offered `garrick_safe_passage` at severity 70 == threshold, so every clock tick wrote
cap=30, and ACT 5's forced `evt_21_iron_legion_advance` (severity 85) was skipped on every
run. Found by the first live `make demo-run-live` (T2.4); fix chosen by the owner
2026-09-17: change the seed, keep the cap (DEC-274 amendment stands).

Raw Python seed data plus the bundled pacing rules — no I/O beyond reading the YAML.
"""

from __future__ import annotations

import json
from pathlib import Path

from demo_game.seeds.seed import _CHAIN_QUESTS, _SOURCE_CHAIN_QUESTS
from demo_game.seeds.seed_npc_data import H2_CHAIN_QUESTS, H2_SOURCE_CHAIN_QUESTS
from npc_engine.engines.story_pacing.pacing_rules_loader import load_pacing_rules

REPO_ROOT = Path(__file__).resolve().parents[3]
PACING_RULES = REPO_ROOT / "src" / "npc_engine" / "engines" / "story_pacing" / "pacing_rules.yaml"
EVENT_POOL = REPO_ROOT / "src" / "npc_engine" / "data" / "event_pool.json"
ACT5_TEMPLATE_ID = "evt_21_iron_legion_advance"
COMPLETED = "completed"


def _seeded_quests() -> list[dict]:
    return [*_CHAIN_QUESTS, *_SOURCE_CHAIN_QUESTS, *H2_SOURCE_CHAIN_QUESTS, *H2_CHAIN_QUESTS]


def test_no_seeded_open_quest_triggers_pacing_suppression() -> None:
    """Every non-completed seeded quest sits below the pacing suppression threshold."""
    threshold = load_pacing_rules(PACING_RULES).high_severity_quest_threshold
    suppressing = [
        (q["id"], q["severity"])
        for q in _seeded_quests()
        if q.get("status") != COMPLETED and q.get("severity", 0) >= threshold
    ]
    assert not suppressing, (
        f"seeded quests at/above pacing threshold {threshold} keep max_event_severity capped "
        f"for the whole demo, blocking ACT 5: {suppressing}"
    )


def test_act5_template_would_exceed_the_suppression_cap() -> None:
    """Pins why the guard above matters: evt_21 cannot fire while pacing is suppressed."""
    cap = load_pacing_rules(PACING_RULES).suppression_event_severity_cap
    templates = json.loads(EVENT_POOL.read_text(encoding="utf-8"))
    (act5,) = [t for t in templates if t["id"] == ACT5_TEMPLATE_ID]
    assert act5["severity"] > cap
