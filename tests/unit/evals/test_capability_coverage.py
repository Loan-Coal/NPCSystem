"""
Module: test_capability_coverage
Layer: test (unit)
Purpose: Verify that every demo-world NPC with at least one grounded knowledge edge has
         at least one capability case (case_pos_* YAML file). The failure message is a
         named work-list for the EVAL-P9.3 authoring session.
         See docs/CAPABILITY_CASES.md for the capability-case contract.
Dependencies: pytest, yaml, pathlib
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASES_DIR = Path(__file__).parents[3] / "evals" / "cases"

# Demo-world NPC IDs that hold at least one grounded knowledge edge.
# Grounding = any of: KNOWS_ABOUT, BELIEVES, HAS_MEMORY, HAS_GOAL, HAS_SECRET.
# Sources:
#   demo_game/seeds/seed.py          — core five + EXP-223 trio
#   demo_game/seeds/seed_npc_data.py — H2.2 six-NPC expansion
# Update this set when new NPCs are added to the demo-world seed.
GROUNDED_DEMO_NPCS: frozenset[str] = frozenset(
    {
        # Core demo-world NPCs
        "mira_innkeeper",
        "aldric_merchant",
        "captain_sorn",
        "lira_fence",
        "old_henryk",
        # EXP-223 expansion
        "sera_barmaid",
        "harwick_guard",
        "nel_pickpocket",
        # H2.2 expansion
        "bren_smith",
        "nessa_priestess",
        "dorn_dockmaster",
        "vex_spymaster",
        "tilda_herbalist",
        "garrick_deserter",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _covered_demo_npcs() -> frozenset[str]:
    """Return NPC IDs that have at least one demo-world case_pos_* file.

    Scans evals/cases/ for files whose name starts with case_pos_ and whose
    seed block has requires_world == "demo".
    """
    covered: set[str] = set()
    for path in sorted(CASES_DIR.glob("case_pos_*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        seed = data.get("seed", {})
        if seed.get("requires_world") == "demo":
            npc_id = seed.get("npc_id")
            if npc_id:
                covered.add(npc_id)
    return frozenset(covered)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_every_grounded_npc_has_a_capability_case() -> None:
    """Every demo-world NPC with grounded knowledge must have a case_pos_* file.

    Fails with a named work-list so EVAL-P9.3 (human authoring session) knows
    exactly which NPCs still need a capability case.
    """
    covered = _covered_demo_npcs()
    uncovered = sorted(GROUNDED_DEMO_NPCS - covered)
    assert not uncovered, (
        "NPCs with grounded knowledge but no capability case "
        "(work-list for EVAL-P9.3 authoring session): "
        + ", ".join(uncovered)
    )
