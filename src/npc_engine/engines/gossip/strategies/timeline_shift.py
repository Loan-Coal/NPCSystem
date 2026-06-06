"""
Module: timeline_shift
Layer: engines
Purpose: Timeline-shift distortion strategy — relocates an event to the distant past.
Does NOT: perform graph I/O or call LLMs. Reads prefix from distortion.yaml via prefix_loader.
Dependencies: engines/gossip/strategies/prefix_loader
Dependencies injected: None.
Used by: distortion_strategy.STRATEGY_REGISTRY
"""

from __future__ import annotations

from npc_engine.engines.gossip.strategies.prefix_loader import get_distortion_prefix

_PREFIX = get_distortion_prefix("timeline_shift")


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
