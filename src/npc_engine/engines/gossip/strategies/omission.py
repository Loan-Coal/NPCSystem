"""
Module: omission
Layer: engines
Purpose: Omission distortion strategy — trims a summary to the first half of its words.
Does NOT: perform I/O, access the graph, or call LLMs.
Dependencies: none
Dependencies injected: None.
Used by: distortion_strategy.STRATEGY_REGISTRY
"""

from __future__ import annotations


class OmissionStrategy:
    """Distortion strategy that drops the latter half of the event summary words.

    Mirrors the legacy _apply_template 'omission' branch exactly:
    ``" ".join(words[: max(1, len(words) // 2)])``.
    """

    def __call__(self, summary: str) -> str:
        """Return the first half of the words in *summary*.

        Args:
            summary: Raw event summary text.

        Returns:
            Truncated summary containing at most ``max(1, len(words) // 2)`` words.
        """
        words = summary.split()
        return " ".join(words[: max(1, len(words) // 2)])


omission = OmissionStrategy()
