"""
Module: exaggeration
Layer: engines
Purpose: Exaggeration distortion strategy — prepends a catastrophic framing prefix.
Does NOT: perform graph I/O or call LLMs. Reads prefix from distortion.yaml via prefix_loader.
Dependencies: engines/gossip/strategies/prefix_loader
Dependencies injected: None.
Used by: distortion_strategy.STRATEGY_REGISTRY
"""

from __future__ import annotations

from npc_engine.engines.gossip.strategies.prefix_loader import get_distortion_prefix

_PREFIX = get_distortion_prefix("exaggeration")


class ExaggerationStrategy:
    """Distortion strategy that amplifies an event with a catastrophic prefix.

    Mirrors the legacy _apply_template 'exaggeration' branch exactly:
    ``f"It was utterly catastrophic: {summary}"``.
    """

    def __call__(self, summary: str) -> str:
        """Return *summary* prepended with the catastrophic framing prefix.

        Args:
            summary: Raw event summary text.

        Returns:
            Exaggerated summary string.
        """
        return f"{_PREFIX}{summary}"


exaggeration = ExaggerationStrategy()
