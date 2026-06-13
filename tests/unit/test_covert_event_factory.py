"""Unit tests for engines.scheming.covert_event_factory (DEC-107 Option A)."""

from __future__ import annotations

from npc_engine.engines.scheming.covert_event_factory import (
    COVERT_SCHEME_EVENT_IS_PUBLIC,
    COVERT_SCHEME_EVENT_SEVERITY,
    COVERT_SCHEME_EVENT_TYPE,
    build_covert_event_props,
)

_REQUIRED_EVENT_FIELDS = {
    "id",
    "summary",
    "severity",
    "location_id",
    "occurred_at",
    "tick_id",
    "event_type",
    "is_public",
    "last_graph_updated_at",
}


def _build(**overrides):
    base = dict(
        event_id="ev_1",
        npc_id="lira_fence",
        goal="rob the vault",
        step_order=2,
        location_id="tavern",
        tick_id=42,
        now_iso="2026-06-13T00:00:00+00:00",
    )
    base.update(overrides)
    return build_covert_event_props(**base)


def test_props_contain_every_required_event_field():
    props = _build()
    assert _REQUIRED_EVENT_FIELDS.issubset(props.keys())


def test_event_type_is_dedicated_covert_type():
    assert _build()["event_type"] == COVERT_SCHEME_EVENT_TYPE
    assert COVERT_SCHEME_EVENT_TYPE == "scheme_advance"


def test_covert_event_is_not_public():
    assert _build()["is_public"] is COVERT_SCHEME_EVENT_IS_PUBLIC
    assert _build()["is_public"] is False


def test_severity_is_below_witness_threshold():
    # Witness/disruption side effects only fire at severity >= 80.
    assert _build()["severity"] == COVERT_SCHEME_EVENT_SEVERITY
    assert _build()["severity"] < 80


def test_summary_includes_npc_goal_and_step():
    props = _build(npc_id="vex", goal="bribe the guard", step_order=3)
    assert "vex" in props["summary"]
    assert "bribe the guard" in props["summary"]
    assert "3" in props["summary"]


def test_event_id_and_location_are_passed_through():
    props = _build(event_id="ev_xyz", location_id="market_square")
    assert props["id"] == "ev_xyz"
    assert props["location_id"] == "market_square"


def test_timestamps_use_now_iso():
    props = _build(now_iso="2026-01-01T12:00:00+00:00")
    assert props["occurred_at"] == "2026-01-01T12:00:00+00:00"
    assert props["last_graph_updated_at"] == "2026-01-01T12:00:00+00:00"


def test_tick_id_passed_through():
    assert _build(tick_id=99)["tick_id"] == 99
