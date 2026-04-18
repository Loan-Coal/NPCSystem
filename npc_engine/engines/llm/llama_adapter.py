"""
llama_adapter.py - Thin Llama wrapper over Mistral-compatible HTTP adapter behavior.

Does NOT: choose backend implementations.

Dependencies injected: base_url, timeout_seconds.
"""

from engines.llm.mistral_adapter import MistralAdapter


class LlamaAdapter(MistralAdapter):
    """Adapter for Llama completion endpoints using shared HTTP implementation."""

    def model_name(self) -> str:
        return "llama8b"
