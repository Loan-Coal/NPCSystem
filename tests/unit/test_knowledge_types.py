"""
test_knowledge_types.py - Unit tests for the shared KnowledgeState contract.

Does NOT: touch Neo4j or run the gossip engine.

Dependencies injected: None.
"""

from __future__ import annotations

from typing import get_args

from npc_engine.common.knowledge_types import (
    KNOWLEDGE_STATE_KNOWS,
    KNOWLEDGE_STATE_RUMOR,
    KnowledgeState,
)


def test_constants_have_expected_values() -> None:
    assert KNOWLEDGE_STATE_KNOWS == "knows"
    assert KNOWLEDGE_STATE_RUMOR == "rumor"


def test_literal_members_are_exactly_knows_and_rumor() -> None:
    assert set(get_args(KnowledgeState)) == {"knows", "rumor"}


def test_consumers_reuse_the_shared_rumor_constant() -> None:
    """prompt_builder + gossip_spread_service must not redefine the value locally."""
    from npc_engine.engines.dialogue import prompt_builder
    from npc_engine.graph import gossip_spread_service

    assert prompt_builder._RUMOR_KNOWLEDGE_STATE == KNOWLEDGE_STATE_RUMOR
    assert gossip_spread_service._KNOWLEDGE_STATE_RUMOR == KNOWLEDGE_STATE_RUMOR
