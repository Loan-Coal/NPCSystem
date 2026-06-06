"""
Module: exaggeration
Layer: engines
Purpose: Exaggeration distortion strategy — prepends a catastrophic framing prefix.
Does NOT: perform I/O, access the graph, or call LLMs.
Dependencies: none
Dependencies injected: None.
Used by: distortion_strategy.STRATEGY_REGISTRY
"""

from __future__ import annotations

_PREFIX = "It was utterly catastrophic: "


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
