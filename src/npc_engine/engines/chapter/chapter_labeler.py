"""
Module: chapter_labeler
Layer: engines
Purpose: Rule-based chapter label generator for use as an LLM fallback.
Does NOT: call LLMs or access the graph.
Dependencies: None (pure computation).
Dependencies injected: none.
Used by: engines.chapter.chapter_engine
"""

from __future__ import annotations


def label_chapter_by_rules(events: list[dict]) -> dict:
    """Return a deterministic chapter label based on dominant event types.

    Args:
        events: List of recent event dicts.

    Returns:
        Dict with ``title``, ``description``, ``theme``.
    """
    if not events:
        return {
            "title": "The Quiet Before",
            "description": "A period of calm between greater storms.",
            "theme": "calm",
        }
    dominant_type = events[0].get("event_type", "unknown")
    theme_map = {
        "battle": ("The Blood Tide", "War sweeps across the land.", "conflict"),
        "assassination": ("Shadows Fall", "A blade in the dark changes everything.", "betrayal"),
        "alliance": ("The Grand Accord", "Unlikely allies forge a new pact.", "alliance"),
        "discovery": ("The Uncharted Path", "Ancient secrets come to light.", "discovery"),
        "disaster": ("The Breaking Storm", "Nature itself turns against the realm.", "crisis"),
    }
    title, description, theme = theme_map.get(
        dominant_type,
        ("A Turning of the Tide", "Events shift the course of history.", "mystery"),
    )
    return {"title": title, "description": description, "theme": theme}
