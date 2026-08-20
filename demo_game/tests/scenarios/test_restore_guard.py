"""
Module: test_restore_guard
Layer: demo_game (tests)
Purpose: Unit tests for the live-writer probe that guards destructive restores (ISSUE-188).
Dependencies: demo_game.restore_guard, pytest, demo_game.tests.conftest fakes
Used by: make test-demo
"""

from __future__ import annotations

from typing import Any

import pytest

from demo_game import restore_guard
from demo_game.tests.conftest import FakeSession, world_clock_row


# ---------------------------------------------------------------------------
# graph_fingerprint
# ---------------------------------------------------------------------------


def _state(node_count: int = 248, rel_count: int = 233, clocks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "node_count": node_count,
        "rel_count": rel_count,
        "clocks": clocks if clocks is not None else [world_clock_row("world", 41)],
    }


def test_fingerprint_reads_counts_and_world_clocks() -> None:
    fingerprint = restore_guard.graph_fingerprint(FakeSession([_state()]))

    assert fingerprint.node_count == 248
    assert fingerprint.rel_count == 233
    assert fingerprint.world_clocks[0].id == "world"
    assert fingerprint.world_clocks[0].tick_id == 41


def test_fingerprint_is_equal_for_an_unchanged_graph() -> None:
    assert restore_guard.graph_fingerprint(FakeSession([_state()])) == restore_guard.graph_fingerprint(
        FakeSession([_state()])
    )


@pytest.mark.parametrize(
    "changed",
    [
        _state(node_count=249),
        _state(rel_count=234),
        _state(clocks=[world_clock_row("world", 42)]),
        _state(clocks=[world_clock_row("world", 41, "2026-08-20T00:00:01Z")]),
        _state(clocks=[world_clock_row("world", 41), world_clock_row("world_village", 3)]),
    ],
)
def test_fingerprint_differs_on_every_tracked_field(changed: dict[str, Any]) -> None:
    reference = restore_guard.graph_fingerprint(FakeSession([_state()]))

    assert restore_guard.graph_fingerprint(FakeSession([changed])) != reference


def test_fingerprint_tolerates_a_world_state_without_a_tick() -> None:
    """The checked-in eval baseline carries no tick_id until the engine has run."""
    session = FakeSession([_state(clocks=[world_clock_row("world", None, None)])])

    fingerprint = restore_guard.graph_fingerprint(session)

    assert fingerprint.world_clocks[0].tick_id is None
    assert fingerprint.world_clocks[0].last_updated_at is None


# ---------------------------------------------------------------------------
# assert_no_live_writer
# ---------------------------------------------------------------------------


def test_stable_graph_passes_the_probe() -> None:
    restore_guard.assert_no_live_writer(FakeSession([_state()]), probe_seconds=12, sleep=lambda _s: None)


def test_a_moving_graph_raises_with_the_change_described() -> None:
    session = FakeSession([_state(), _state(clocks=[world_clock_row("world", 42)])])

    with pytest.raises(restore_guard.LiveWriterDetectedError) as excinfo:
        restore_guard.assert_no_live_writer(session, probe_seconds=12, sleep=lambda _s: None)

    assert excinfo.value.changes == ["WorldState 'world'.tick_id: 41 -> 42"]


def test_probe_waits_the_configured_window() -> None:
    slept: list[float] = []

    restore_guard.assert_no_live_writer(FakeSession([_state()]), probe_seconds=7, sleep=slept.append)

    assert slept == [7]


def test_probe_of_zero_seconds_reads_nothing_at_all() -> None:
    session = FakeSession([_state()])

    restore_guard.assert_no_live_writer(session, probe_seconds=0, sleep=lambda _s: None)

    assert session.session_calls == []


# ---------------------------------------------------------------------------
# describe_change
# ---------------------------------------------------------------------------


def test_describe_change_reports_counts_and_appearing_world_states() -> None:
    before = restore_guard.graph_fingerprint(FakeSession([_state(node_count=139, clocks=[])]))
    after = restore_guard.graph_fingerprint(FakeSession([_state(node_count=248)]))

    changes = restore_guard.describe_change(before, after)

    assert "node_count: 139 -> 248" in changes
    assert "WorldState 'world': appeared" in changes


def test_describe_change_is_empty_for_identical_fingerprints() -> None:
    fingerprint = restore_guard.graph_fingerprint(FakeSession([_state()]))

    assert restore_guard.describe_change(fingerprint, fingerprint) == []


# ---------------------------------------------------------------------------
# probe_seconds
# ---------------------------------------------------------------------------


def test_probe_seconds_defaults_to_longer_than_one_autopilot_tick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(restore_guard.PROBE_SECONDS_ENV, raising=False)

    assert restore_guard.probe_seconds() == restore_guard.PROBE_SECONDS_DEFAULT
    # config.py TICK_INTERVAL_SECONDS = 10: the window must outlast one tick, or a
    # running autopilot can slip through the probe unseen.
    assert restore_guard.PROBE_SECONDS_DEFAULT > 10


def test_probe_seconds_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(restore_guard.PROBE_SECONDS_ENV, "5")

    assert restore_guard.probe_seconds() == 5


@pytest.mark.parametrize("value", ["soon", "-1"])
def test_probe_seconds_rejects_bad_settings(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(restore_guard.PROBE_SECONDS_ENV, value)

    with pytest.raises(ValueError):
        restore_guard.probe_seconds()
