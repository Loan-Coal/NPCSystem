"""
Package: graph_rag
Layer: retrieval
Purpose: Graph-augmented retrieval: RAG pipeline, subgraph assembly, memory temporal annotation, and reindex jobs.
Public surface: graph_rag_retrieve, assemble_tier_a_context, annotate_memory_ages, ReindexJobService.
Does NOT: access Neo4j directly or call LLMs.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .graph_rag import graph_rag_retrieve
from .subgraph_retriever import assemble_tier_a_context
from .memory_temporal import annotate_memory_ages
from .reindex_job_service import ReindexJobService

__all__ = [
    'graph_rag_retrieve',
    'assemble_tier_a_context',
    'annotate_memory_ages',
    'ReindexJobService',
]
