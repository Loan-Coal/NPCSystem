"""
Package: context
Layer: retrieval
Purpose: Context assembly, scoring, compression, serialisation, and budget enforcement for LLM prompts.
Public surface: ContextItem, MergedContext, merge_context, estimate_tokens, serialize_json, parse_node_identity, CHARS_PER_TOKEN_ESTIMATE, _LOW_VALUE_FIELDS, COMPRESSION_SUFFIX, log_context_metrics, ContextMetrics, ContextRelevanceCandidate, rank_context_candidates, rank_tier_items, serialize_context, enforce_final_serialized_budget_with_context, ContextCompressionCache, fill_to_budget, EmbeddingIndexProtocol, build_serialized_context.
Does NOT: access Neo4j directly or call LLMs.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .context_merger import ContextItem, MergedContext, merge_context
from .context_utils import estimate_tokens, serialize_json, parse_node_identity, CHARS_PER_TOKEN_ESTIMATE, _LOW_VALUE_FIELDS
from .context_compression import (
    COMPRESSION_SUFFIX, ContextCompressionCache, build_compression_cache_key,
    MIN_COMPRESSED_CHARS, _compress_text, _extract_graph_timestamp,
)
from .context_budget_enforcer import ContextBudgetError, enforce_context_budget, fill_to_budget
from .context_metrics import (
    CONTEXT_CACHE_HITS_METRIC,
    CONTEXT_CACHE_MISSES_METRIC,
    record_compression_metrics,
    record_context_metrics,
)
from .context_relevance_engine import (
    ContextRelevanceCandidate, rank_context_candidates,
    MAX_COMPONENT_SCORE, MIN_COMPONENT_SCORE, score_candidate,
)
from .context_scoring import (
    rank_tier_items, _build_candidate, _extract_recency_score,
    _extract_relation_score, _extract_severity_score, _infer_proximity_hops,
    _normalize_ratio, _quest_score,
)
from .context_serializer import serialize_context
from .context_builder_helpers import enforce_final_serialized_budget_with_context, expand_query, keyword_overlap, rerank_by_keyword
from .context_protocols import EmbeddingIndexProtocol
from .context_builder import build_serialized_context, _enforce_final_serialized_budget, _estimate_tokens

__all__ = [
    'ContextItem',
    'MergedContext',
    'merge_context',
    'estimate_tokens',
    'serialize_json',
    'parse_node_identity',
    'CHARS_PER_TOKEN_ESTIMATE',
    '_LOW_VALUE_FIELDS',
    'COMPRESSION_SUFFIX',
    'ContextCompressionCache',
    'build_compression_cache_key',
    'ContextBudgetError',
    'enforce_context_budget',
    'fill_to_budget',
    'CONTEXT_CACHE_HITS_METRIC',
    'CONTEXT_CACHE_MISSES_METRIC',
    'record_compression_metrics',
    'record_context_metrics',
    'ContextRelevanceCandidate',
    'rank_context_candidates',
    'rank_tier_items',
    'serialize_context',
    'enforce_final_serialized_budget_with_context',
    'EmbeddingIndexProtocol',
    'build_serialized_context',
]
