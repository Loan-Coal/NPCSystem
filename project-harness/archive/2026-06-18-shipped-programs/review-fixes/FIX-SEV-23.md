# FIX-SEV-23 — Split `LLMClientProtocol` (ISP) into generate/structured/stream

**Severity:** MEDIUM · **Decision:** DEC-121 (split now, pre-SDK-freeze)

## Problem
`LLMClientProtocol` bundles `generate`, `generate_structured`, `stream`, `health_check`, `model_name`. A
streaming-only or text-only backend must stub the methods it can't support (LSP risk; false-passing mocks).
DEC-121: split so engines depend only on the surface they use — the roadmap adds new backends.

## Current shape (verify against code now)
- `src/npc_engine/engines/llm/protocols.py` — single `LLMClientProtocol` with all five members.
- Consumers: `DialogueLLMClient` uses `generate_structured` + `stream`; other engines use only `generate`.
- Concrete adapters (ollama, mock) implement the full protocol today.

## Steps
1. Define `LLMGenerateProtocol` (`generate`, `model_name`, `health_check`),
   `LLMStructuredProtocol(LLMGenerateProtocol)` (+`generate_structured`),
   `LLMStreamProtocol(LLMGenerateProtocol)` (+`stream`). All `@runtime_checkable` Protocols.
2. Narrow each consumer's type hint to the smallest protocol it needs (engines → `LLMGenerateProtocol`;
   dialogue → the structured/stream ones). Keep concrete adapters implementing everything they support.
3. Ensure the mock adapter's behavior contract still matches the real adapter for each split protocol (LSP).

## Verification
- mypy proves Protocol conformance at injection sites; add a test that a minimal object implementing only
  `LLMGenerateProtocol` satisfies an engine that needs just generation.
- `pytest tests/ -k "llm or dialogue or protocol" -q` then `make check`.

## Blast radius
`engines/llm/protocols.py`, the LLM adapters, `DialogueLLMClient`, engine constructors' type hints, mocks.
Interface-shape change for the protocol — do before any SDK client builds against it.
