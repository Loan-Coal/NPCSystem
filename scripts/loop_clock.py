"""
Module: loop_clock
Layer: harness
Purpose: Resolve the overnight loop's stop deadline — the next occurrence of a wall-clock
    stop time, strictly after the moment the run starts — as an absolute epoch instant.
Dependencies: stdlib datetime/argparse/re.
Used by: scripts/expand_loop.sh (startup only; the loop's per-iteration check is a plain
    integer comparison against `date +%s` and never re-enters Python).

WHY THIS IS NOT DONE IN SHELL
-----------------------------
The old guard compared time-of-day (`HHMMSS >= 080000 && HHMMSS < 120000`), which has no
notion of WHICH 08:00. A run started at 11:21 matched the window and exited having done
nothing. Correct "next occurrence" arithmetic needs real calendar rollover — month, year
and leap-day — which is worth having under test rather than inline in bash.

WHY THERE ARE NO TIMEZONES HERE
-------------------------------
Measured on this machine: Git Bash ships no tzdata, so `TZ=Europe/Paris date` — and
`TZ=Foo/Bar date`, identically — silently returns UTC. Python's zoneinfo cannot resolve
IANA names either (no `tzdata` package). The only clock that is correct without adding a
dependency is naive OS local time, which is what this module uses throughout. Deadlines
cross the shell boundary as epoch seconds, which are absolute and carry no zone at all,
so the shell side compares them against `date +%s` with no zone handling of its own.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, time, timedelta

# Spellings that turn the guard off entirely, mirroring how an empty START_AT disables
# the start wait. Without this the only way to disable a stop was an off-label time.
DISABLE_KEYWORDS = frozenset({"", "none", "off", "never"})

# HH:MM with optional :SS. Deliberately strict — no am/pm, no bare hour, no sign.
STOP_SPEC_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")

SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60
DISPLAY_FORMAT = "%Y-%m-%d %H:%M:%S"

EXIT_OK = 0
EXIT_BAD_SPEC = 2


def parse_stop_spec(spec: str) -> time | None:
    """Parse a --stop-at value into a wall-clock time, or None when disabled.

    Args:
        spec: "HH:MM", "HH:MM:SS", or a disable keyword ("none", "off", "never", "").
    Returns:
        The stop time, or None if the guard is disabled.
    Raises:
        ValueError: If the value is neither a valid time nor a disable keyword. Callers
            must halt rather than assume a default: silently falling back to "stop now"
            would reproduce the bug this module exists to fix.
    """
    cleaned = spec.strip()
    if cleaned.lower() in DISABLE_KEYWORDS:
        return None

    match = STOP_SPEC_RE.match(cleaned)
    if match is None:
        raise ValueError(f"not a HH:MM[:SS] time or a disable keyword: {spec!r}")

    hour, minute, second = match.group(1), match.group(2), match.group(3)
    return time(int(hour), int(minute), int(second or 0))


def next_stop(now: datetime, stop: time) -> datetime:
    """The next occurrence of ``stop``, strictly after ``now``.

    Starting at exactly the stop time yields a full 24 hours rather than zero: a run
    launched on the boundary is a run the operator wants, not one to refuse.

    Args:
        now: The moment the run starts, as naive local time.
        stop: The wall-clock time of day at which to stop starting new work.
    Returns:
        The deadline, as naive local time with microseconds zeroed.
    """
    candidate = now.replace(
        hour=stop.hour, minute=stop.minute, second=stop.second, microsecond=0
    )
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def format_delta(seconds: int) -> str:
    """Render a duration as a compact "18h39m" / "39m" for the startup log line."""
    if seconds <= 0:
        return "0m"
    hours, remainder = divmod(seconds, SECONDS_PER_HOUR)
    minutes = remainder // SECONDS_PER_MINUTE
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def describe(epoch: int, now: datetime | None = None) -> str:
    """Render a deadline epoch as "2026-08-06 08:00:00 (in 18h39m)" for logging."""
    moment = datetime.fromtimestamp(epoch)
    reference = now or datetime.now()
    delta = int((moment - reference).total_seconds())
    return f"{moment.strftime(DISPLAY_FORMAT)} (in {format_delta(delta)})"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[3].strip())
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--next-stop",
        metavar="SPEC",
        help="Print the next occurrence of SPEC as epoch seconds; empty if disabled.",
    )
    group.add_argument(
        "--describe",
        metavar="EPOCH",
        type=int,
        help="Print an epoch as a human-readable local time plus time-until.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0, or 2 when --next-stop cannot be parsed."""
    args = _build_parser().parse_args(argv)

    if args.describe is not None:
        print(describe(args.describe))
        return EXIT_OK

    try:
        stop = parse_stop_spec(args.next_stop)
    except ValueError as exc:
        print(f"invalid --stop-at: {exc}", file=sys.stderr)
        return EXIT_BAD_SPEC

    # An empty line is the disabled signal: the shell reads it into an empty STOP_EPOCH.
    print("" if stop is None else int(next_stop(datetime.now(), stop).timestamp()))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
