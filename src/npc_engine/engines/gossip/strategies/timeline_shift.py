"""
Module: timeline_shift
Layer: engines
Purpose: Timeline-shift distortion strategy — relocates an event to the distant past.
Does NOT: perform I/O, access the graph, or call LLMs.
Dependencies: none
Dependencies injected: None.
Used by: distortion_strategy.STRATEGY_REGISTRY
"""

from __future__ import annotations

_PREFIX = "Long ago, "


class TimelineShiftStrategy:
    """Distortion strategy that displaces an event into the distant past.

    Mirrors the legacy _apply_template 'timeline_shift' branch exactly:
    ``f"Long ago, {summary}"``.
    """

    def __call__(self, summary: str) -> str:
        """Return *summary* prepended with the 'Long ago' temporal prefix.

        Args:
            summary: Raw event summary text.

        Returns:
            Timeline-shifted summary string.
        """
        return f"{_PREFIX}{summary}"


timeline_shift = TimelineShiftStrategy()
