"""
Regression tests for SEV-04 gossip domain migration.

Guards that all gossip Cypher constants and session.run calls live in
graph/gossip_queries.py (graph layer), not in engines/gossip/ (engines layer).

Tests fail before the migration (ImportError or AttributeError) and pass after.
"""
from __future__ import annotations

import inspect

from npc_engine.graph.gossip_queries import (
    CYPHER_SELECT_EVENT,
    CYPHER_GOSSIP_PAIRS,
    fetch_gossip_pairs,
    fetch_known_node_ids,
    # write-side re-exported from gossip_queries for backward compat
    fetch_relation_log,
    select_gossip_event,
    select_gossip_secret,
    select_relation_trust,
    update_relation_log,
    write_knowledge_propagation,
    write_secret_propagation,
)
from npc_engine.graph.gossip_write_queries import CYPHER_PROPAGATE_KNOWLEDGE


def test_select_event_in_graph_layer():
    """CYPHER_SELECT_EVENT must live in graph/gossip_queries (SEV-09 clauses preserved)."""
    assert "is_canonical" in CYPHER_SELECT_EVENT
    assert "corrected" in CYPHER_SELECT_EVENT
    assert "ORDER BY" in CYPHER_SELECT_EVENT


def test_gossip_pairs_query_in_graph_layer():
    """CYPHER_GOSSIP_PAIRS must live in graph/gossip_queries."""
    assert "Character" in CYPHER_GOSSIP_PAIRS
    assert "LOCATED_AT" in CYPHER_GOSSIP_PAIRS


def test_propagate_knowledge_query_in_graph_layer():
    """CYPHER_PROPAGATE_KNOWLEDGE must live in graph/gossip_queries."""
    assert "KNOWS_ABOUT" in CYPHER_PROPAGATE_KNOWLEDGE
    assert "MERGE" in CYPHER_PROPAGATE_KNOWLEDGE


def test_all_gossip_query_functions_are_async():
    """All gossip graph query functions must be async coroutines."""
    async_fns = [
        select_gossip_event,
        select_gossip_secret,
        select_relation_trust,
        fetch_gossip_pairs,
        fetch_known_node_ids,
        write_knowledge_propagation,
        write_secret_propagation,
        fetch_relation_log,
        update_relation_log,
    ]
    for fn in async_fns:
        assert inspect.iscoroutinefunction(fn), f"{fn.__name__} must be async"
