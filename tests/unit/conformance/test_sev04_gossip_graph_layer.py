"""
Regression tests for SEV-04 gossip domain migration.

Guards that all gossip Cypher constants and session.run calls live in
graph/gossip_queries.py (graph layer), not in engines/gossip/ (engines layer).

Tests fail before the migration (ImportError or AttributeError) and pass after.
"""
from __future__ import annotations

from npc_engine.graph.gossip.gossip_queries import CYPHER_GOSSIP_PAIRS
from npc_engine.graph.gossip.gossip_write_queries import CYPHER_PROPAGATE_KNOWLEDGE


def test_gossip_pairs_query_in_graph_layer():
    """CYPHER_GOSSIP_PAIRS must live in graph/gossip_queries."""
    assert "Character" in CYPHER_GOSSIP_PAIRS
    assert "LOCATED_AT" in CYPHER_GOSSIP_PAIRS


def test_propagate_knowledge_query_in_graph_layer():
    """CYPHER_PROPAGATE_KNOWLEDGE must live in graph/gossip_queries."""
    assert "KNOWS_ABOUT" in CYPHER_PROPAGATE_KNOWLEDGE
    assert "MERGE" in CYPHER_PROPAGATE_KNOWLEDGE


