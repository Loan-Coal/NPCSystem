"""
Module: test_sandbox_loop
Layer: demo_game.tests
Purpose: Unit tests for SandboxLoop — background auto-tick thread.
Dependencies: demo_game.sandbox_loop
Used by: pytest
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from demo_game.sandbox_loop import SandboxLoop


def _make_client() -> MagicMock:
    """Return a mock EngineClient that records advance_clock calls."""
    client = MagicMock()
    client.advance_clock = MagicMock(return_value={"current_tick": 1})
    return client


def test_sandbox_loop_calls_advance_clock_repeatedly() -> None:
    """start() → sleep → stop(): advance_clock(1) called at least 3 times."""
    client = _make_client()
    loop = SandboxLoop(client=client, interval_s=0.05)

    loop.start()
    time.sleep(0.2)
    loop.stop()

    call_count = client.advance_clock.call_count
    assert call_count >= 3, f"Expected >= 3 calls, got {call_count}"
    client.advance_clock.assert_called_with(1)


def test_sandbox_loop_stops_calling_after_stop() -> None:
    """No more advance_clock calls happen after stop()."""
    client = _make_client()
    loop = SandboxLoop(client=client, interval_s=0.05)

    loop.start()
    time.sleep(0.2)
    loop.stop()

    count_after_stop = client.advance_clock.call_count
    time.sleep(0.15)
    count_later = client.advance_clock.call_count

    assert count_later == count_after_stop, (
        f"Expected no calls after stop(), got {count_later - count_after_stop} more"
    )


def test_sandbox_loop_stop_idempotent() -> None:
    """Calling stop() twice does NOT raise."""
    client = _make_client()
    loop = SandboxLoop(client=client, interval_s=0.05)

    loop.start()
    time.sleep(0.1)
    loop.stop()
    loop.stop()  # must not raise


def test_sandbox_loop_is_running_false_after_stop() -> None:
    """is_running is False after stop()."""
    client = _make_client()
    loop = SandboxLoop(client=client, interval_s=0.05)

    loop.start()
    assert loop.is_running is True

    loop.stop()
    assert loop.is_running is False


def test_sandbox_loop_not_running_before_start() -> None:
    """is_running is False before start() is called."""
    client = _make_client()
    loop = SandboxLoop(client=client, interval_s=0.05)
    assert loop.is_running is False
