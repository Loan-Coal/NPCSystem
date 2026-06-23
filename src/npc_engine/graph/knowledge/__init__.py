"""
Package: graph.knowledge
Layer: graph
Purpose: Beliefs, causality, witnessing, and knowledge writes.
Public surface: submodules — knowledge_writer,belief_queries,belief_service,causality_queries,causality_service,witnessed_queries,witnessed_service.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
