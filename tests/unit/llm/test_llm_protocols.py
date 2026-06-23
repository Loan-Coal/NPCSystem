"""
test_llm_protocols.py - ISP split of the LLM client protocol (SEV-23 / DEC-121).

Does NOT: make network calls. Uses minimal stub objects to probe Protocol membership.

Dependencies injected: None.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from npc_engine.engines.llm.protocols import (
    LLMClientProtocol,
    LLMGenerateProtocol,
    LLMStreamProtocol,
    LLMStructuredProtocol,
)


class _GenerateOnly:
    """Backend that only supports plain-text generation."""

    async def generate(self, prompt: str, max_tokens: int, temperature: float,
                        top_p: float | None = None, stop_sequences: list[str] | None = None,
                        system: str | None = None) -> str:
        return ""

    async def health_check(self) -> bool:
        return True

    def model_name(self) -> str:
        return "gen-only"


class _StructuredOnly(_GenerateOnly):
    async def generate_structured(self, prompt: str, schema: dict[str, Any], max_tokens: int,
                                  top_p: float | None = None, stop_sequences: list[str] | None = None,
                                  system: str | None = None) -> dict[str, Any]:
        return {}


class _Full(_StructuredOnly):
    def stream(self, prompt: str, max_tokens: int, temperature: float,
               top_p: float | None = None, stop_sequences: list[str] | None = None,
               system: str | None = None) -> AsyncIterator[str]:
        ...


def test_generate_only_satisfies_only_generate_protocol() -> None:
    obj = _GenerateOnly()
    assert isinstance(obj, LLMGenerateProtocol)
    assert not isinstance(obj, LLMStructuredProtocol)
    assert not isinstance(obj, LLMStreamProtocol)
    assert not isinstance(obj, LLMClientProtocol)


def test_structured_only_satisfies_structured_not_stream() -> None:
    obj = _StructuredOnly()
    assert isinstance(obj, LLMStructuredProtocol)
    assert not isinstance(obj, LLMStreamProtocol)
    assert not isinstance(obj, LLMClientProtocol)


def test_full_backend_satisfies_every_protocol() -> None:
    obj = _Full()
    assert isinstance(obj, LLMGenerateProtocol)
    assert isinstance(obj, LLMStructuredProtocol)
    assert isinstance(obj, LLMStreamProtocol)
    assert isinstance(obj, LLMClientProtocol)
