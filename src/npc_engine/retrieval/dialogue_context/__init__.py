"""
Package: dialogue_context
Layer: retrieval
Purpose: Per-session dialogue context cache and Neo4j-backed adapter.
Public surface: DialogueContextCache, PartialDialogueContextCache, Neo4jDialogueContextAdapter.
Does NOT: access Neo4j directly or call LLMs.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .dialogue_context_cache import DialogueContextCache, PartialDialogueContextCache
from .dialogue_context_adapter import Neo4jDialogueContextAdapter

__all__ = [
    'DialogueContextCache',
    'PartialDialogueContextCache',
    'Neo4jDialogueContextAdapter',
]
