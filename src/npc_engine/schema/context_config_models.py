"""
context_config_models.py - Typed models for v1.4 context relevance and budget settings.

Does NOT: load files from disk or execute runtime prompt logic.

Dependencies injected: None.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator


MIN_RATIO = 0.0
MAX_RATIO = 1.0
WEIGHTS_SUM_TARGET = 1.0
WEIGHTS_SUM_TOLERANCE = 1e-6


class TierBudgetTokens(BaseModel):
    """Per-tier token budgets used by the context pipeline."""

    tier_a: int = Field(gt=0)
    tier_b: int = Field(gt=0)
    tier_c: int = Field(gt=0)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class RelevanceWeights(BaseModel):
    """Deterministic relevance scoring weights for context selection."""

    recency: float = Field(ge=MIN_RATIO, le=MAX_RATIO)
    severity: float = Field(ge=MIN_RATIO, le=MAX_RATIO)
    proximity: float = Field(ge=MIN_RATIO, le=MAX_RATIO)
    relation: float = Field(ge=MIN_RATIO, le=MAX_RATIO)
    quest: float = Field(ge=MIN_RATIO, le=MAX_RATIO)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "RelevanceWeights":
        """Enforce that all relevance weights sum to exactly 1.0.

        Returns:
            Validated RelevanceWeights instance.

        Raises:
            ValueError: if the sum of all weights deviates from 1.0 by more than
                WEIGHTS_SUM_TOLERANCE.
        """

        weights_sum = (
            self.recency
            + self.severity
            + self.proximity
            + self.relation
            + self.quest
        )
        if abs(weights_sum - WEIGHTS_SUM_TARGET) > WEIGHTS_SUM_TOLERANCE:
            raise ValueError("relevance_weights must sum to 1.0")
        return self


class LLMConfig(BaseModel):
    """Root v1.4 configuration model for context relevance and budget policy."""

    prompt_schema_version: str
    compression_prompt_version: str
    tier_budget_tokens: TierBudgetTokens
    session_turns_budget_tokens: int = Field(gt=0)
    compression_trigger_ratio: float = Field(gt=MIN_RATIO, le=MAX_RATIO)
    max_proximity_hops: int = Field(ge=0)
    relevance_weights: RelevanceWeights

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
