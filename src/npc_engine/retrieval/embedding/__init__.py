"""
Package: embedding
Layer: retrieval
Purpose: Vector store, sentence encoding, cross-encoder reranking, topic classification, and embedding index.
Public surface: VectorSearchResult, VectorStoreProtocol, create_vector_store, embed, cross_encoder_reranker, detect_dialogue_profile, EMBED_DIMENSION, EmbeddingIndex, EmbeddingReconciler.
Does NOT: access Neo4j directly or call LLMs.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .vector_store_protocol import VectorSearchResult, VectorStoreProtocol
from .vector_store_factory import create_vector_store
from .sentence_encoder import embed
from . import cross_encoder_reranker
from .cross_encoder_reranker import rerank
from .embedding_index import _embed_text
from .vector_store_factory import InMemoryVectorStore
from .topic_classifier import detect_dialogue_profile
from .embedding_index import EMBED_DIMENSION, EmbeddingIndex
from .embedding_reconciler import EmbeddingReconciler

__all__ = [
    'VectorSearchResult',
    'VectorStoreProtocol',
    'create_vector_store',
    'embed',
    'cross_encoder_reranker',
    'detect_dialogue_profile',
    'EMBED_DIMENSION',
    'EmbeddingIndex',
    'EmbeddingReconciler',
]
