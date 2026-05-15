"""
llama_adapter.py - Thin Llama wrapper over Mistral-compatible HTTP adapter behavior.

Does NOT: choose backend implementations.

Dependencies injected: base_url, model_name, timeout_seconds.
"""

from npc_engine.engines.llm.mistral_adapter import MistralAdapter


class LlamaAdapter(MistralAdapter):
    """Adapter for Llama completion endpoints using shared HTTP implementation."""
