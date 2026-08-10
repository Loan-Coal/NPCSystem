"""
Module: test_capability_coverage
Layer: test (unit)
Purpose: Ratchet the capability-case coverage of demo-world NPCs that hold grounded
         knowledge. Coverage may only improve: an NPC that loses its case_pos_* file,
         or a newly-grounded NPC added to the seed without a case, turns this red.
         The still-uncovered NPCs are the named work-list for EVAL-P9.3.
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

# Grounded NPCs that do **not** yet have a capability case — the EVAL-P9.3 work-list.
#
# This is a ratchet baseline, not a target. It exists because EVAL-P9.1 landed this
# module asserting `uncovered == set()` while EVAL-P9.3 (the human authoring session that
# produces the missing cases) is `live`-flagged and therefore unreachable to the overnight
# loop. The result was a gate that could not go green by any action the loop could take:
# it was red from 2026-08-08 and halted the phase gate after EVAL-P11 and EVAL-P12.
# DEC-159 §4 is explicit that a new evals gate lands against a ratchet baseline and keeps
# `make check` green; this brings the module into line with that. See DEC-161.
#
# RATCHET DOWN when a case is authored: delete the NPC from this set in the same commit
# that adds its case_pos_* file. `test_uncovered_baseline_has_no_stale_entries` fails if
# you forget, so the baseline cannot silently over-state the remaining work.
#
# CLOSED 2026-08-10 by EVAL-P20.2: the last nine entries (bren_smith, dorn_dockmaster,
# garrick_deserter, harwick_guard, nel_pickpocket, nessa_priestess, sera_barmaid,
# tilda_herbalist, vex_spymaster) were removed in the commit that authored their cases.
# Every grounded demo NPC now has one, so `test_capability_coverage_never_regresses` is
# back to the flat `uncovered == set()` assertion DEC-161 had to relax. Keep it empty:
# an addition here is a deliberate deferral and needs a note saying why.
#
# Coverage is not the same as capability. These cases mostly FAIL against the live
# engine because the dialogue context arrives with no beliefs, goals or memories in it
# — see ISSUE-145. The ratchet tracks whether a case exists, never whether it passes.
UNCOVERED_BASELINE: frozenset[str] = frozenset()


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


def test_capability_coverage_never_regresses() -> None:
    """No grounded demo NPC may lose — or start out without — a capability case.

    Red means one of two real regressions, never "the authoring session is unfinished":
    a case_pos_* file was deleted or had its seed block changed, or an NPC was added to
    GROUNDED_DEMO_NPCS without a case and without a deliberate baseline edit.
    """
    uncovered = GROUNDED_DEMO_NPCS - _covered_demo_npcs()
    regressed = sorted(uncovered - UNCOVERED_BASELINE)
    assert not regressed, (
        "grounded NPCs lost their capability case (or were seeded without one): "
        + ", ".join(regressed)
        + " — restore the case_pos_* file, or add the NPC to UNCOVERED_BASELINE "
        "deliberately with a note saying why its case is deferred."
    )


def test_uncovered_baseline_has_no_stale_entries() -> None:
    """The ratchet may only tighten: a baselined NPC that gained a case must be removed.

    This is what stops UNCOVERED_BASELINE from rotting into a permanent excuse — the
    commit that authors a case is forced to shrink the work-list in the same diff.
    """
    uncovered = GROUNDED_DEMO_NPCS - _covered_demo_npcs()
    now_covered = sorted(UNCOVERED_BASELINE - uncovered)
    assert not now_covered, (
        "these NPCs now have a capability case but are still baselined as uncovered: "
        + ", ".join(now_covered)
        + " — delete them from UNCOVERED_BASELINE to ratchet the gate down."
    )
    unknown = sorted(UNCOVERED_BASELINE - GROUNDED_DEMO_NPCS)
    assert not unknown, (
        "UNCOVERED_BASELINE names NPCs that are not in GROUNDED_DEMO_NPCS: "
        + ", ".join(unknown)
    )
