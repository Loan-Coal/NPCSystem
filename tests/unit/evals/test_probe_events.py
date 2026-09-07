"""
Module: test_probe_events
Layer: test (unit)
Purpose: Tests for evals/probe_events.py — EventsProbe's batch seeding, the
         events/tick + severity_mean + orphan_rate metrics, and the known-events
         invariant.
Dependencies: pytest, unittest.mock, probe_events (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from unittest.mock import MagicMock

from probe_events import EVENTS_PROBE_FACTORIES, EventsProbe


def _ok(payload: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


def _client_with_knowers(known_event_ids: set[str]) -> MagicMock:
    client = MagicMock()
    client.post.return_value = _ok({"data": {}})

    def _get(url: str, **kwargs: object) -> MagicMock:
        dst_id = kwargs.get("params", {}).get("dst_id")
        has_edge = dst_id in known_event_ids
        return _ok({"data": [{"src_id": "x"}] if has_edge else []})

    client.get.side_effect = _get
    return client


def test_engine_name_is_events() -> None:
    assert EventsProbe().engine_name == "events"


def test_measure_before_drive_returns_empty() -> None:
    probe = EventsProbe()
    probe.setup(MagicMock())
    assert probe.measure(MagicMock()) == {}


def test_drive_creates_one_event_per_tick_and_marks_every_other_known() -> None:
    probe = EventsProbe()
    probe.setup(MagicMock())
    client = _client_with_knowers(set())

    probe.drive(client, ticks=4)

    assert len(probe._event_ids) == 4
    assert len(probe._known_event_ids) == 2


def test_measure_reports_severity_mean_and_orphan_rate() -> None:
    probe = EventsProbe()
    probe.setup(MagicMock())
    seed_client = MagicMock()
    seed_client.post.return_value = _ok({"data": {}})
    probe.drive(seed_client, ticks=4)

    client = _client_with_knowers(set(probe._known_event_ids))
    metrics = probe.measure(client)

    assert metrics["events_created_per_tick"] == 1.0
    assert metrics["severity_mean"] == (20 + 45 + 65 + 80) / 4
    assert metrics["orphan_rate"] == 0.5


def test_invariant_holds_when_every_known_event_still_has_its_edge() -> None:
    probe = EventsProbe()
    probe.setup(MagicMock())
    seed_client = MagicMock()
    seed_client.post.return_value = _ok({"data": {}})
    probe.drive(seed_client, ticks=2)

    client = _client_with_knowers(set(probe._known_event_ids))
    assert probe.invariants["known_events_have_an_edge"](client) is True


def test_invariant_fails_when_a_known_event_lost_its_edge() -> None:
    probe = EventsProbe()
    probe.setup(MagicMock())
    seed_client = MagicMock()
    seed_client.post.return_value = _ok({"data": {}})
    probe.drive(seed_client, ticks=2)

    client = _client_with_knowers(set())  # no edges survive
    assert probe.invariants["known_events_have_an_edge"](client) is False


def test_events_probe_factory_is_registered() -> None:
    assert "events" in EVENTS_PROBE_FACTORIES
    probe = EVENTS_PROBE_FACTORIES["events"](MagicMock())
    assert probe.engine_name == "events"
