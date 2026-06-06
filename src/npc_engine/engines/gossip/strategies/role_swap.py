"""
Module: role_swap
Layer: engines
Purpose: Role-swap distortion strategy — frames the event as having happened in reverse.
Dependencies: none
Used by: distortion_strategy.STRATEGY_REGISTRY
"""

from __future__ import annotations

_PREFIX = "They say the opposite happened: "


class RoleSwapStrategy:
    """Distortion strategy that inverts the narrative framing of an event.

    Mirrors the legacy _apply_template 'role_swap' branch exactly:
    ``f"They say the opposite happened: {summary}"``.
    """

    def __call__(self, summary: str) -> str:
        """Return *summary* prepended with the opposite-framing prefix.

        Args:
            summary: Raw event summary text.

        Returns:
            Role-swapped summary string.
        """
        return f"{_PREFIX}{summary}"


role_swap = RoleSwapStrategy()
