"""Tests for ForcedEventTick: Act 5 fires a named event template deterministically."""

from __future__ import annotations

from unittest.mock import MagicMock

from demo_game.runners.run_scenes import ForcedEventTick


def _make_runner(created: int = 1, dry_run: bool = False) -> MagicMock:
    runner = MagicMock()
    runner.dry_run = dry_run
    runner.client._graph_timeout = 15.0
    resp = MagicMock()
    resp.json.return_value = {"success": True, "data": {"tick_id": 4, "created": created}}
    runner.client._client.post.return_value = resp
    return runner


def test_dry_run_makes_no_http_call() -> None:
    runner = _make_runner(dry_run=True)
    ForcedEventTick(name="t", template_id="evt_x").execute(runner)
    runner.client._client.post.assert_not_called()


def test_posts_the_template_id_to_the_event_tick_route() -> None:
    runner = _make_runner()
    ForcedEventTick(name="t", template_id="evt_x").execute(runner)
    args, kwargs = runner.client._client.post.call_args
    assert args[0] == "/v1/admin/batch/event_tick"
    assert kwargs["json"] == {"template_id": "evt_x"}
    assert "[skip]" not in runner.print_ok.call_args.args[0]


def test_reports_a_skipped_event_instead_of_claiming_success() -> None:
    runner = _make_runner(created=0)
    ForcedEventTick(name="t", template_id="evt_x").execute(runner)
    assert runner.print_ok.call_args.args[0].startswith("[skip]")
