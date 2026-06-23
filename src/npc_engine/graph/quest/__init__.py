"""
Package: graph.quest
Layer: graph
Purpose: Quest nodes, chains, generation, and verification.
Public surface: submodules — quest_queries,quest_writer,quest_chain_queries,quest_generation_queries,quest_node_queries,quest_node_service,quest_verification_queries,need_quest_queries.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
