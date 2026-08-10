"""
Module: test_reset_snapshot
Layer: test (unit)
Purpose: Unit tests for e2e/scripts/reset_snapshot.py — the pure snapshot-diff
         logic behind the EVAL-P12.1 reset fidelity measurement. The rule under
         test is that only components the scenario actually mutated carry
         information, and that an unobservable store is never silently dropped.
Dependencies: pathlib, sys, pytest, reset_snapshot (e2e/scripts/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "e2e" / "scripts"))

from reset_snapshot import (  # noqa: E402
    RESET_TARGET_PROPERTIES,
    UNOBSERVABLE_STORES,
    changed,
    classify,
    digest,
    snapshot_world_state,
    unknown_entries,
    unwrap,
)


# ---------------------------------------------------------------------------
# digest / unwrap
# ---------------------------------------------------------------------------


def test_digest_is_stable_across_key_order() -> None:
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})


def test_digest_distinguishes_different_payloads() -> None:
    assert digest({"a": 1}) != digest({"a": 2})


def test_unwrap_returns_the_envelope_data() -> None:
    assert unwrap({"success": True, "data": [1, 2]}) == [1, 2]


def test_unwrap_passes_through_a_bare_payload() -> None:
    assert unwrap([1, 2]) == [1, 2]


# ---------------------------------------------------------------------------
# world_state is split so the reset's own targets are visible separately
# ---------------------------------------------------------------------------


def test_world_state_reset_targets_get_their_own_components() -> None:
    components = snapshot_world_state([{"epoch": "war", "active_conditions": "[]", "year": 1}])
    for prop in RESET_TARGET_PROPERTIES:
        assert f"world_state.{prop}" in components
    assert "world_state.other_properties" in components


def test_changing_only_a_non_target_property_leaves_the_targets_identical() -> None:
    before = snapshot_world_state([{"epoch": "war", "active_conditions": "[]", "year": 1}])
    after = snapshot_world_state([{"epoch": "war", "active_conditions": "[]", "year": 2}])
    assert before["world_state.epoch"] == after["world_state.epoch"]
    assert before["world_state.other_properties"] != after["world_state.other_properties"]


def test_an_absent_world_state_node_still_yields_components() -> None:
    components = snapshot_world_state([])
    assert set(components) >= {f"world_state.{p}" for p in RESET_TARGET_PROPERTIES}


# ---------------------------------------------------------------------------
# changed
# ---------------------------------------------------------------------------


def test_changed_reports_only_differing_components() -> None:
    assert changed({"a": "1", "b": "2"}, {"a": "1", "b": "3"}) == ("b",)


def test_a_component_present_in_only_one_snapshot_counts_as_changed() -> None:
    """An appearing or vanishing component is a difference, not a gap."""
    assert changed({"a": "1"}, {"a": "1", "new": "9"}) == ("new",)
    assert changed({"a": "1", "gone": "9"}, {"a": "1"}) == ("gone",)


# ---------------------------------------------------------------------------
# classify — the core rule
# ---------------------------------------------------------------------------


def test_a_component_restored_to_baseline_is_cleared() -> None:
    cleared, surviving = classify({"x": "0"}, {"x": "1"}, {"x": "0"})
    assert cleared == ("x",)
    assert surviving == ()


def test_a_component_not_restored_is_surviving() -> None:
    cleared, surviving = classify({"x": "0"}, {"x": "1"}, {"x": "1"})
    assert cleared == ()
    assert surviving == ("x",)


def test_a_component_the_scenario_never_touched_appears_in_neither_list() -> None:
    """It proves nothing about the reset either way, so claiming it as cleared
    would overstate the reset and claiming it as surviving would overstate the
    damage."""
    cleared, surviving = classify({"x": "0"}, {"x": "0"}, {"x": "0"})
    assert cleared == ()
    assert surviving == ()


def test_a_component_changed_to_a_third_value_by_the_reset_is_surviving() -> None:
    """Not restored is not cleared, even if the reset moved it somewhere new."""
    cleared, surviving = classify({"x": "0"}, {"x": "1"}, {"x": "2"})
    assert surviving == ("x",)


def test_classify_handles_the_mixed_case() -> None:
    baseline = {"kept": "0", "lost": "0", "untouched": "0"}
    mutated = {"kept": "1", "lost": "1", "untouched": "0"}
    after = {"kept": "0", "lost": "1", "untouched": "0"}
    cleared, surviving = classify(baseline, mutated, after)
    assert cleared == ("kept",)
    assert surviving == ("lost",)


# ---------------------------------------------------------------------------
# Unobservable stores are named, never dropped
# ---------------------------------------------------------------------------


def test_every_unobservable_store_carries_a_reason() -> None:
    for name, reason in UNOBSERVABLE_STORES:
        assert name and reason, f"{name!r} has no recorded reason"


def test_unknown_entries_cover_every_unobservable_store() -> None:
    entries = unknown_entries()
    assert len(entries) == len(UNOBSERVABLE_STORES)
    for name, _reason in UNOBSERVABLE_STORES:
        assert f"unknown:{name}" in entries


def test_the_session_and_dialogue_caches_are_among_the_unobservable() -> None:
    """Named explicitly: these two are the ones whose omission would turn a
    PARTIAL reset into a false FULL."""
    names = {name for name, _ in UNOBSERVABLE_STORES}
    assert {"session_store", "dialogue_context_cache"} <= names
