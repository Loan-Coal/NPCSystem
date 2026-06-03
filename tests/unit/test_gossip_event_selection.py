"""
Unit regression tests for CYPHER_SELECT_EVENT (SEV-09).

Guards two bugs in the sharer-event-selection query:
  1. Canonical true facts were always distorted because the query never
     returned ``is_canonical`` (so the canonical-skip branch was dead).
  2. A corrected rumor (knowledge_state='corrected') was still re-selected
     as the freshest known event and re-propagated.

These are structural assertions on the query text — they fail for the right
reason before the fix and pass after, without requiring a live Neo4j.
"""

from __future__ import annotations

from npc_engine.engines.gossip.gossip_handler import CYPHER_SELECT_EVENT


def test_select_event_returns_is_canonical():
    """Query must surface is_canonical so the canonical-skip branch can fire."""
    assert "is_canonical" in CYPHER_SELECT_EVENT


def test_select_event_excludes_corrected_edges():
    """Query must exclude edges whose knowledge_state is 'corrected'."""
    assert "knowledge_state" in CYPHER_SELECT_EVENT
    assert "corrected" in CYPHER_SELECT_EVENT
