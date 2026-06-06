"""
Module: role_swap
Layer: engines
Purpose: Role-swap distortion strategy — frames the event as having happened in reverse.
Does NOT: perform graph I/O or call LLMs. Reads prefix from distortion.yaml via prefix_loader.
Dependencies: engines/gossip/strategies/prefix_loader
Dependencies injected: None.
Used by: distortion_strategy.STRATEGY_REGISTRY
"""

from __future__ import annotations

from npc_engine.engines.gossip.strategies.prefix_loader import get_distortion_prefix

_PREFIX = get_distortion_prefix("role_swap")


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
