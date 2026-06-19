"""
llm_config_models.py - Deprecated re-export shim for context_config_models.
Layer: config
Purpose: Deprecated re-export shim for context_config_models.

Does NOT: define any models; delegates entirely to context_config_models.

Dependencies injected: none.
"""
from __future__ import annotations

from npc_engine.schema.context_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens

__all__ = ["LLMConfig", "RelevanceWeights", "TierBudgetTokens"]
