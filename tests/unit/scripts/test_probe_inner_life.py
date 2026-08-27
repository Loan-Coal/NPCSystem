"""
Module: tests.unit.scripts.test_probe_inner_life
Layer: test (unit)
Purpose: Pin the inner-life probe's PARSE against a recorded debug-retrieval response, so
         a change to the endpoint breaks the probe loudly instead of silently reporting
         zeros.
Dependencies: pytest; scripts.probe_inner_life
Used by: make test (pytest discovery)

This is the specific defect ISSUE-216 records: the P8 reconstruction of this probe parsed
the wrong response shape and reported a false 0/8 across the board before being corrected.
`beliefs`, `goals` and `memories` are NESTED under the `npc` slot, and `current_location`
is nested TWO levels down under `npc.profile` — three depths, none of them top level. The
P9 rewrite got `current_location` wrong on its first run and reported a false 0/8 against
DEC-212's recorded 8/8, which is the argument for this module existing.

Every declared slot is also emitted UNCONDITIONALLY (P6), so the presence of a key proves
nothing and only its content does.

Does NOT: perform HTTP, hit the engine, or read the graph.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_probe():
    """Load scripts/probe_inner_life.py by PATH, without touching sys.path.

    `scripts/` has no `__init__.py`, so importing it normally would mean inserting the
    REPO ROOT on sys.path. That has a non-obvious side effect measured here: it makes
    `evals` resolvable as a top-level package, which widens coverage's measured source
    from 18,291 statements to 23,487 and drops the reported total from 88% to 69% —
    a 19-point "regression" caused entirely by a test's import mechanics. A path-based
    load has no such reach.
    """
    path = Path(__file__).resolve().parents[3] / "scripts" / "probe_inner_life.py"
    spec = importlib.util.spec_from_file_location("_probe_inner_life_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_probe = _load_probe()
INNER_LIFE_SLOTS = _probe.INNER_LIFE_SLOTS
PROBE_NPCS = _probe.PROBE_NPCS
extract_slots = _probe.extract_slots


def _item(key: str, value: object) -> dict:
    return {
        "key": key,
        "tier": "unknown",
        "priority": 0,
        "text": value if isinstance(value, str) else json.dumps(value),
    }


def _response(**overrides: object) -> dict:
    """A debug-retrieval body shaped like the live one, populated by default."""
    npc = {
        "beliefs": [{"content": "The thieves guild is planning something", "confidence": 90}],
        "goals": [{"description": "Hold the barracks"}],
        "memories": [{"summary": "Drilled the recruits"}],
        "top_need": {},
        "profile": {"id": "captain_sorn", "current_location": "Guard Barracks"},
    }
    npc.update(overrides.pop("npc", {}))  # type: ignore[arg-type]
    body = {
        "npc_id": "captain_sorn",
        "query": "what news",
        "player_id": "player_demo",
        "retrieval_profile": "default",
        "total_tokens": 1019,
        "context_items": [
            _item("npc", npc),
            _item("nearby_npcs", [{"id": "harwick_guard"}]),
            _item("retrieved_context", [{"id": "lira_fence"}]),
            _item("player_relation", {"affection": 0, "interaction_count": 2}),
            _item("player_reputation", [{"faction_name": "crown", "standing": 40}]),
            _item("propagated_reputation", [{"act": "helped"}]),
            _item("world", {"day": 1}),
        ],
        "context_receipt": None,
    }
    body.update(overrides)
    return body


def test_the_four_headline_slots_are_read_from_inside_the_npc_object() -> None:
    """The exact mistake the P8 reconstruction made. Read at top level, all four are
    absent and the probe reports a false 0/8."""
    slots = extract_slots(_response())
    assert slots["beliefs"] is True
    assert slots["goals"] is True
    assert slots["memories"] is True
    assert slots["current_location"] is True


def test_the_three_reputation_slots_are_reported() -> None:
    """Structurally invisible before P9, because the route passed no player_id."""
    slots = extract_slots(_response())
    assert slots["player_relation"] is True
    assert slots["player_reputation"] is True
    assert slots["propagated_reputation"] is True


def test_an_emitted_but_empty_slot_counts_as_ABSENT() -> None:
    """Every declared slot is emitted unconditionally (P6), so key presence proves
    nothing. A probe that counted keys would report 8/8 on an engine carrying nothing."""
    slots = extract_slots(
        _response(
            context_items=[
                _item("npc", {"beliefs": [], "goals": [], "memories": [],
                              "profile": {"id": "x", "current_location": ""}}),
                _item("nearby_npcs", []),
                _item("retrieved_context", []),
                _item("player_relation", {}),
                _item("player_reputation", []),
                _item("propagated_reputation", []),
            ],
        )
    )
    assert not any(slots.values())


def test_every_declared_slot_is_reported_even_when_the_response_omits_it() -> None:
    """A missing slot must read as absent, not raise. A KeyError mid-probe would leave
    the roster half-measured and the totals silently wrong."""
    slots = extract_slots({"context_items": []})
    assert set(slots) == set(INNER_LIFE_SLOTS)
    assert not any(slots.values())


def test_a_malformed_slot_payload_does_not_crash_the_probe() -> None:
    """`_safe_parse` can hand a raw string through when compression truncates JSON
    (ISSUE-214). The probe must survive it and report the slot as present."""
    slots = extract_slots(
        {"context_items": [_item("retrieved_context", '{"id":"lira_fence"...truncated')]}
    )
    assert slots["retrieved_context"] is True


def test_the_probe_roster_is_eight_npcs_and_fixed() -> None:
    """"8/8, was 0/975" is only meaningful against a roster that does not move between
    phases."""
    assert len(PROBE_NPCS) == 8
    assert len(set(PROBE_NPCS)) == 8


@pytest.mark.parametrize("slot", INNER_LIFE_SLOTS)
def test_each_reported_slot_has_a_stable_name(slot: str) -> None:
    """Guards a rename in the slot table from silently dropping a column from the
    report — the probe would keep printing a full matrix with one fewer measurement."""
    assert slot and slot == slot.lower()
