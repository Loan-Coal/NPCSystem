"""Tests for the overnight loop's stop-deadline clock.

The bug these pin: `past_morning_stop` used to compare time-of-day, so it had no notion
of WHICH 08:00. A run started at 11:21 saw "11:21 >= 08:00" and refused to start work,
having done nothing. The deadline is now an absolute instant resolved once at startup —
the next occurrence of the stop time STRICTLY AFTER the run starts.

Every case freezes `now` explicitly. Nothing here reads the wall clock.
"""

from __future__ import annotations

import sys
from datetime import datetime, time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from loop_clock import next_stop, parse_stop_spec  # noqa: E402


class TestNextStop:
    """The next-occurrence rule, which is the whole point of the module."""

    def test_morning_run_stops_tomorrow(self) -> None:
        # The reported bug: started 09:00, must run the night, not refuse to start.
        assert next_stop(datetime(2026, 8, 5, 9, 0, 0), time(8, 0, 0)) == datetime(
            2026, 8, 6, 8, 0, 0
        )

    def test_pre_dawn_run_stops_today(self) -> None:
        assert next_stop(datetime(2026, 8, 5, 6, 0, 0), time(8, 0, 0)) == datetime(
            2026, 8, 5, 8, 0, 0
        )

    def test_evening_run_stops_next_morning(self) -> None:
        assert next_stop(datetime(2026, 8, 5, 20, 0, 0), time(8, 0, 0)) == datetime(
            2026, 8, 6, 8, 0, 0
        )

    def test_exact_boundary_gives_a_full_day(self) -> None:
        # Decided: a run starting at exactly the stop time gets 24h, not zero.
        assert next_stop(datetime(2026, 8, 5, 8, 0, 0), time(8, 0, 0)) == datetime(
            2026, 8, 6, 8, 0, 0
        )

    def test_one_second_before_boundary_stops_immediately_after(self) -> None:
        assert next_stop(datetime(2026, 8, 5, 7, 59, 59), time(8, 0, 0)) == datetime(
            2026, 8, 5, 8, 0, 0
        )

    def test_sub_second_past_boundary_rolls_over(self) -> None:
        # 08:00:00.5 is past 08:00:00, so today's instant is gone.
        now = datetime(2026, 8, 5, 8, 0, 0, 500_000)
        assert next_stop(now, time(8, 0, 0)) == datetime(2026, 8, 6, 8, 0, 0)

    def test_deadline_carries_no_microseconds(self) -> None:
        now = datetime(2026, 8, 5, 9, 30, 15, 123_456)
        assert next_stop(now, time(8, 0, 0)).microsecond == 0

    def test_crosses_month_end(self) -> None:
        assert next_stop(datetime(2026, 8, 31, 9, 0, 0), time(8, 0, 0)) == datetime(
            2026, 9, 1, 8, 0, 0
        )

    def test_crosses_year_end(self) -> None:
        assert next_stop(datetime(2026, 12, 31, 23, 0, 0), time(8, 0, 0)) == datetime(
            2027, 1, 1, 8, 0, 0
        )

    def test_crosses_leap_day(self) -> None:
        assert next_stop(datetime(2028, 2, 28, 9, 0, 0), time(8, 0, 0)) == datetime(
            2028, 2, 29, 8, 0, 0
        )

    def test_honours_minutes_and_seconds(self) -> None:
        assert next_stop(datetime(2026, 8, 5, 9, 0, 0), time(8, 30, 15)) == datetime(
            2026, 8, 6, 8, 30, 15
        )
        assert next_stop(datetime(2026, 8, 5, 8, 15, 0), time(8, 30, 15)) == datetime(
            2026, 8, 5, 8, 30, 15
        )

    def test_midnight_stop_time(self) -> None:
        assert next_stop(datetime(2026, 8, 5, 23, 0, 0), time(0, 0, 0)) == datetime(
            2026, 8, 6, 0, 0, 0
        )


class TestParseStopSpec:
    """Boundary validation: a bad --stop-at must be loud, never silently permissive."""

    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            ("08:00:00", time(8, 0, 0)),
            ("08:00", time(8, 0)),  # the form in the script's own usage header
            ("8:00", time(8, 0)),
            ("23:59:59", time(23, 59, 59)),
            ("00:00:00", time(0, 0, 0)),
            ("  08:00:00  ", time(8, 0, 0)),
        ],
    )
    def test_accepts_valid_times(self, spec: str, expected: time) -> None:
        assert parse_stop_spec(spec) == expected

    @pytest.mark.parametrize("spec", ["none", "NONE", "off", "never", "", "   "])
    def test_disable_keywords_return_none(self, spec: str) -> None:
        assert parse_stop_spec(spec) is None

    @pytest.mark.parametrize(
        "spec", ["25:00:00", "08:60", "tomorrow", "8am", "08-00-00", "-1:00", "08:00:00:00"]
    )
    def test_rejects_garbage(self, spec: str) -> None:
        # Failing closed (stop immediately) would reproduce the very bug being fixed,
        # so an unparseable spec must raise and let the caller halt at preflight.
        with pytest.raises(ValueError):
            parse_stop_spec(spec)
