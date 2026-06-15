"""
Module: knowledge_types
Layer: common
Purpose: Canonical KnowledgeState Literal + named constants for the "knows"/"rumor"
         knowledge-state value used on propagation edges and in LLM context (L3-10).
Does NOT: read the graph, instantiate engines, or perform I/O.
Dependencies: None (zero-dep shared contract).
Dependencies injected: None.
Used by: engines.gossip.knowledge_propagator, engines.gossip.gossip_handler,
         engines.dialogue.prompt_builder, graph.gossip_spread_service.
"""

from __future__ import annotations

from typing import Literal

KnowledgeState = Literal["knows", "rumor"]

KNOWLEDGE_STATE_KNOWS: KnowledgeState = "knows"
KNOWLEDGE_STATE_RUMOR: KnowledgeState = "rumor"
