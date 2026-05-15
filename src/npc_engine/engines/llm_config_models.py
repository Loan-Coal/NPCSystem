"""
Module: llm_config_models
Layer: engines
Purpose: Typed Pydantic models for per-engine LLM configuration YAML files.
Does NOT: load files from disk or select LLM adapters.
Dependencies injected: None.
Used by: engines.llm_config_loader, engines.llm.factory.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


_VALID_BACKENDS = Literal["ollama", "mistral7b", "llama8b", "mock"]
_VALID_FALLBACK_POLICIES = Literal["graceful_degradation", "fail_fast"]


class EngineModelParams(BaseModel):
    """LLM adapter identity and per-call generation parameters for one engine."""

    backend: _VALID_BACKENDS
    model: str = Field(min_length=1)
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(gt=0)
    top_p: float = Field(ge=0.0, le=1.0)
    stop_sequences: list[str]

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class EnginePromptRef(BaseModel):
    """Reference to the versioned prompt template used by this engine."""

    name: str = Field(min_length=1)
    version: int = Field(gt=0)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class EngineFallbackPolicy(BaseModel):
    """Degradation policy applied when the primary LLM tier fails."""

    policy: _VALID_FALLBACK_POLICIES
    tiers: list[str] = Field(min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class EngineTimeoutsMs(BaseModel):
    """Per-tier timeout budgets in milliseconds."""

    full: int = Field(gt=0)
    graph_only: int | None = Field(default=None, gt=0)
    canned: int | None = Field(default=None, gt=0)
    deterministic: int | None = Field(default=None, gt=0)

    model_config = ConfigDict(frozen=True, extra="forbid")


class EngineModelConfig(BaseModel):
    """Root per-engine LLM configuration model validated from YAML."""

    engine: str = Field(min_length=1)
    llm: EngineModelParams
    prompt: EnginePromptRef
    output_schema_ref: str = Field(min_length=1)
    fallback: EngineFallbackPolicy
    timeouts_ms: EngineTimeoutsMs

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
