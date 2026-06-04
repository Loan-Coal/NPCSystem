"""
contract_models.py - Typed models for machine-readable engine contracts.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: load contract files from disk.

Dependencies injected: None.
"""

from pydantic import BaseModel, ConfigDict, Field


class IdempotencyContract(BaseModel):
    """Idempotency behavior contract for a single engine."""

    key_required: bool
    replay_behavior: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class EngineContract(BaseModel):
    """Top-level contract model validated from YAML documents."""

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    inputs: list[str] = Field(min_length=1)
    outputs: list[str] = Field(min_length=1)
    side_effects: list[str] = Field(min_length=1)
    idempotency: IdempotencyContract
    auth_scope: str = Field(min_length=1)
    error_contract: list[str] = Field(min_length=1)
    tests: list[str] = Field(min_length=1)
    uses_llm: bool = False

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
