#!/usr/bin/env python
"""
Module: check_engine_census
Layer: harness (repo-level dev tool, outside the package layer model)
Purpose: Assert that every engine directory under src/npc_engine/engines/ is classified
         and reachable — tick engines wired into TickScheduler, non-tick engines imported
         by the API layer.  Fails loudly on any unclassified directory so that dead code
         cannot accumulate silently (finding L10-03, rules 3 and 7).
Dependencies: stdlib only (argparse, pathlib, re, sys).
Used by: `make check-engine-census`, scripts/loop_gates.py.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Explicit classification tables — every table entry is a conscious decision.
# ---------------------------------------------------------------------------

# Infrastructure-support dirs: no live caller required.
INFRA_EXEMPT_DIRS: frozenset[str] = frozenset({"ports", "contracts", "llm", "tts"})

# Non-tick engine dirs: must be imported by at least one file under src/npc_engine/api/.
# emotion declares no run_tick and lives at api/routes/dialogue/npc_state.py (T4.2).
NON_TICK_DIRS: frozenset[str] = frozenset(
    {
        "dialogue",
        "economy",
        "emotion",
        "idempotency",
        "interaction",
        "knowledge_learning",
        "quest",
        "relationship",
    }
)

# All known tick engine directories.  An engine dir absent from this set and from the
# two sets above makes the script exit 1 with UNCLASSIFIED — a conscious addition is
# required before it can pass.
TICK_DIRS: frozenset[str] = frozenset(
    {
        "agenda",
        "chapter",
        "director",
        "events",
        "faction_politics",
        "gossip",
        "investigation",
        "memory",
        "memory_consolidation",
        "need",
        "planning",
        "player_model",
        "proactive_dialogue",
        "quest_generation",
        "reputation",
        "routine",
        "scheming",
        "story_pacing",
        "treaty",
        # Sprint-2 (T4.1) deletions — present in the pre-sprint tree, absent from main.
        # Kept here so --root checks against that tree still classify them as tick engines
        # and report the expected violations (deception, currency were never in the
        # scheduler; the rest were wired but semantically dead — see T6.1 for runtime
        # checks).
        "clique",
        "currency",
        "deception",
        "mood",
        "skill",
    }
)

# Tick engine dirs whose tick-scheduler name differs from the directory name.
# All names in each list must appear as quoted string literals in tick_scheduler.py.
DIR_TO_TICK_NAMES: dict[str, list[str]] = {
    "need": ["need_decay"],
    "memory": ["memory_decay"],
    "scheming": ["scheme_advance"],
    "investigation": ["scheme_detection"],
    "events": ["event"],
    "planning": ["goal_formation"],
    "quest_generation": ["event_quest", "need_quest", "world_state_quest"],
    "agenda": ["agenda", "intent_formation"],
    # Historical mappings (Sprint-2 deletions).
    "skill": ["skill_progression"],
    "mood": ["mood_contagion"],
}

# ---------------------------------------------------------------------------
# Relative paths (stable regardless of --root value)
# ---------------------------------------------------------------------------

_ENGINES_REL: Path = Path("src") / "npc_engine" / "engines"
_SCHEDULER_REL: Path = Path("src") / "npc_engine" / "scheduler" / "tick_scheduler.py"
_API_DEPS_ENG_REL: Path = Path("src") / "npc_engine" / "api" / "dependencies_engines"
_API_DEPS_ADV_REL: Path = Path("src") / "npc_engine" / "api" / "dependencies_advanced"
_API_REL: Path = Path("src") / "npc_engine" / "api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tick_names_for(dir_name: str) -> list[str]:
    """Return the tick-scheduler name(s) expected for dir_name."""
    return DIR_TO_TICK_NAMES.get(dir_name, [dir_name])


def _read_py_tree(directory: Path) -> str:
    """Concatenate all .py files under directory; return empty string if absent."""
    if not directory.exists():
        return ""
    parts: list[str] = []
    for py_file in sorted(directory.rglob("*.py")):
        parts.append(py_file.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _imports_engine_dir(dir_name: str, text: str) -> bool:
    """Return True if text contains an import from engines.<dir_name>."""
    return bool(re.search(r"engines\." + re.escape(dir_name), text))


def _tick_name_present(tick_name: str, scheduler_text: str) -> bool:
    """Return True if tick_name appears as a quoted string in scheduler_text."""
    return bool(re.search(r'"' + re.escape(tick_name) + r'"', scheduler_text))


# ---------------------------------------------------------------------------
# Per-dir checks
# ---------------------------------------------------------------------------


def _check_tick_dir(dir_name: str, root: Path) -> list[str]:
    """Return violations for a tick engine directory."""
    scheduler_path = root / _SCHEDULER_REL
    if not scheduler_path.exists():
        return [f"{dir_name}: tick_scheduler.py not found at {scheduler_path}"]

    scheduler_text = scheduler_path.read_text(encoding="utf-8", errors="replace")
    violations: list[str] = []

    for tick_name in _tick_names_for(dir_name):
        if not _tick_name_present(tick_name, scheduler_text):
            violations.append(
                f"{dir_name}: tick name '{tick_name}' not found as a string literal"
                " in tick_scheduler.py — engine is unwired or dead"
            )

    deps_text = _read_py_tree(root / _API_DEPS_ENG_REL) + "\n" + _read_py_tree(root / _API_DEPS_ADV_REL)
    if not _imports_engine_dir(dir_name, deps_text):
        violations.append(
            f"{dir_name}: engine not imported in any api/dependencies_engines/ or"
            " api/dependencies_advanced/ file — not wired into the composition root"
        )

    return violations


def _check_non_tick_dir(dir_name: str, root: Path) -> list[str]:
    """Return violations for a non-tick (API-reachable) engine directory."""
    api_text = _read_py_tree(root / _API_REL)
    if not _imports_engine_dir(dir_name, api_text):
        return [
            f"{dir_name}: non-tick engine not imported by any file under"
            " src/npc_engine/api/ — unreachable from the API layer"
        ]
    return []


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def check_census(root: Path) -> list[str]:
    """Run the full census check against root and return all violation messages.

    Args:
        root: Repository root to check.  Defaults to the repo root when called
              from the CLI; pass a tmp_path in tests to avoid git operations.

    Returns:
        List of violation strings.  Empty list means the census is clean.
    """
    engines_dir = root / _ENGINES_REL
    if not engines_dir.exists():
        return [f"engines directory not found: {engines_dir}"]

    violations: list[str] = []
    for entry in sorted(engines_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        dir_name = entry.name
        if dir_name in INFRA_EXEMPT_DIRS:
            continue
        if dir_name in NON_TICK_DIRS:
            violations.extend(_check_non_tick_dir(dir_name, root))
        elif dir_name in TICK_DIRS:
            violations.extend(_check_tick_dir(dir_name, root))
        else:
            violations.append(
                f"{dir_name}: UNCLASSIFIED — add explicitly to INFRA_EXEMPT_DIRS,"
                " NON_TICK_DIRS, or TICK_DIRS in scripts/check_engine_census.py"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument list; defaults to sys.argv[1:].

    Returns:
        0 on clean census, 1 on any violation.
    """
    parser = argparse.ArgumentParser(
        description="Check that every engine directory is classified and reachable."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of scripts/).",
    )
    args = parser.parse_args(argv)

    violations = check_census(args.root)
    for violation in violations:
        print(f"FAIL {violation}")
    if violations:
        print(f"\n{len(violations)} violation(s) found.")
        return 1
    print("OK engine census")
    return 0


if __name__ == "__main__":
    sys.exit(main())
