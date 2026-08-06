"""
Module: test_case_annotations
Layer: test (unit)
Purpose: Validate that ≥15 guard cases carry a non-empty relevant_node_ids list,
         and that every referenced ID exists in the demo-world seed.
Dependencies: pytest, yaml, pathlib, demo_game.seeds.seed, demo_game.seeds.seed_npc_data
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASES_DIR = Path(__file__).parents[3] / "evals" / "cases"
MIN_ANNOTATED = 15
_GUARD_PREFIXES = ("case_adv_", "case_neg_")
_KNOWN_EVENTS = frozenset(["northern_war_begins", "northern_war", "market_fire"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_guard_cases() -> list[dict]:
    """Load all case_adv_* and case_neg_* YAML files as parsed dicts."""
    files = sorted(
        f
        for f in CASES_DIR.glob("case_*.yaml")
        if f.stem.startswith(_GUARD_PREFIXES)
    )
    return [yaml.safe_load(f.read_text(encoding="utf-8")) for f in files]


def _annotated(cases: list[dict]) -> list[dict]:
    """Return cases that carry a non-empty relevant_node_ids list."""
    return [
        c
        for c in cases
        if isinstance(c.get("relevant_node_ids"), list) and len(c["relevant_node_ids"]) > 0
    ]


def _seed_node_ids() -> frozenset[str]:
    """Return all node IDs present in the demo-world seed."""
    from demo_game.constants import (
        LOC_ID_CHAPEL,
        NPC_ID_HARWICK_GUARD,
        NPC_ID_NEL_PICKPOCKET,
        NPC_ID_SERA_BARMAID,
    )
    from demo_game.seeds import seed as seed_module
    from demo_game.seeds.seed_npc_data import H2_FACTIONS, H2_LOCATIONS, H2_NPCS

    ids: set[str] = set()
    for t in seed_module._NPCS:
        ids.add(t[0])
    for t in H2_NPCS:
        ids.add(t[0])
    ids.update([NPC_ID_SERA_BARMAID, NPC_ID_HARWICK_GUARD, NPC_ID_NEL_PICKPOCKET])
    for t in seed_module._LOCATIONS:
        ids.add(t[0])
    for t in H2_LOCATIONS:
        ids.add(t[0])
    ids.add(LOC_ID_CHAPEL)
    for t in seed_module._FACTIONS:
        ids.add(t[0])
    for t in seed_module._MILITARY_FACTIONS:
        ids.add(t[0])
    for t in H2_FACTIONS:
        ids.add(t[0])
    ids.update(_KNOWN_EVENTS)
    ids.update(
        [
            seed_module._WORLD_STATE_ID,
            seed_module._PLAYER_ID,
            seed_module._AMULET_ID,
            seed_module._ALDRIC_QUEST_ID,
            seed_module._SPICE_ID,
            seed_module._DECEPTION_BELIEF_ID,
            seed_module._DECEPTION_GOAL_ID,
        ]
    )
    return frozenset(ids)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_annotated_case_count_is_at_least_15() -> None:
    """≥15 guard cases must carry a non-empty relevant_node_ids list."""
    cases = _load_guard_cases()
    annotated = _annotated(cases)
    assert len(annotated) >= MIN_ANNOTATED, (
        f"Only {len(annotated)} guard cases have relevant_node_ids; need ≥{MIN_ANNOTATED}. "
        "Add the key to more guard cases (case_adv_* / case_neg_*)."
    )


def test_relevant_node_ids_all_exist_in_seed() -> None:
    """Every node ID listed in relevant_node_ids must exist in the demo-world seed."""
    cases = _load_guard_cases()
    annotated = _annotated(cases)
    valid_ids = _seed_node_ids()
    errors: list[str] = []
    for case in annotated:
        case_id = case.get("case_id", "<unknown>")
        for node_id in case["relevant_node_ids"]:
            if node_id not in valid_ids:
                errors.append(f"{case_id}: unknown node id '{node_id}'")
    assert not errors, (
        "Some relevant_node_ids reference IDs not in the demo-world seed:\n"
        + "\n".join(errors)
    )


def test_unannotated_cases_load_unchanged() -> None:
    """Cases without relevant_node_ids must still parse to valid case dicts."""
    cases = _load_guard_cases()
    unannotated = [c for c in cases if "relevant_node_ids" not in c]
    for case in unannotated:
        assert "case_id" in case, f"Case missing case_id: {case}"
        assert "seed" in case, f"Case {case.get('case_id')} missing seed block"
        assert "input" in case, f"Case {case.get('case_id')} missing input block"


def test_guard_case_total_is_37() -> None:
    """Guard-case count must remain 37 (regression guard for accidental deletion)."""
    cases = _load_guard_cases()
    assert len(cases) == 37, (
        f"Expected 37 guard cases, found {len(cases)}. "
        "Do not delete guard cases without updating this count."
    )
