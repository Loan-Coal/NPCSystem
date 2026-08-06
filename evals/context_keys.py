"""
Module: context_keys
Layer: evals (evaluation harness)
Purpose: Shared utility for extracting node IDs from context item key strings.
         Keys follow the pattern ``prefix:node_id`` (e.g. ``rag:northern_war_begins``,
         ``character:mira_innkeeper``) or bare node ID strings with no prefix.
Dependencies: (none — zero-dependency utility)
Used by: evals.retrieval_runner, evals.retrieval_join (EVAL-P4.2)
"""

from __future__ import annotations


def node_id_from_key(key: str) -> str:
    """Extract the leaf node ID from a context item key.

    Keys follow the pattern ``prefix:node_id`` (e.g. ``character:mira_innkeeper``,
    ``location:loc_tavern``, ``rag:northern_war_begins``) or bare strings.
    Returns the last colon-separated segment, or the full key when no colon is present.

    Args:
        key: A ContextItem key string.

    Returns:
        The trailing node ID substring after the last colon, or the full key
        when no colon is present.
    """
    return key.rsplit(":", 1)[-1]
