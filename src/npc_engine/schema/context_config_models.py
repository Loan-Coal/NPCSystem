"""
context_config_models.py - Typed models for v1.4 context relevance and budget settings.
Layer: config
Purpose: (auto-detected — review)

Does NOT: load files from disk or execute runtime prompt logic.

Dependencies injected: None.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Built-in weight profiles. Engines declare which profile to use via
# relevance_weight_profile in their YAML config.
DEFAULT_WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "default":              {"recency": 0.30, "severity": 0.20, "proximity": 0.20, "relation": 0.20, "quest": 0.10},
    "investigation":        {"recency": 0.15, "severity": 0.30, "proximity": 0.35, "relation": 0.10, "quest": 0.10},
    "political":            {"recency": 0.20, "severity": 0.20, "proximity": 0.15, "relation": 0.30, "quest": 0.15},
    "social":               {"recency": 0.30, "severity": 0.15, "proximity": 0.20, "relation": 0.25, "quest": 0.10},
    # RPG-tuned profiles: selected automatically by topic_classifier for dialogue,
    # or declared explicitly in engine llm_config.yaml.
    "rpg_dialogue_social":  {"recency": 0.25, "severity": 0.15, "proximity": 0.15, "relation": 0.35, "quest": 0.10},
    "rpg_dialogue_quest":   {"recency": 0.20, "severity": 0.20, "proximity": 0.15, "relation": 0.15, "quest": 0.30},
    "rpg_narrative":        {"recency": 0.30, "severity": 0.30, "proximity": 0.15, "relation": 0.15, "quest": 0.10},
    "rpg_memory":           {"recency": 0.35, "severity": 0.30, "proximity": 0.15, "relation": 0.15, "quest": 0.05},
    "rpg_quest_gen":        {"recency": 0.15, "severity": 0.30, "proximity": 0.20, "relation": 0.15, "quest": 0.20},
}


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
    explicit: float = Field(ge=MIN_RATIO, le=MAX_RATIO, default=0.0)

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
            + self.explicit
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
    recency_game_day_horizon: int = Field(gt=0, default=365)
    default_weight_profile: str = Field(default="default")
    weight_profiles: dict[str, RelevanceWeights] = Field(default_factory=dict)
    # Fraction of PROMPT_TOKEN_BUDGET allocated to each tier (soft caps).
    # tier_c receives the remainder: 1.0 - tier_a_fraction - tier_b_fraction.
    # Override per-engine in the engine's llm_config.yaml for tuning.
    tier_a_fraction: float = Field(default=0.55, gt=0.0, le=1.0)
    tier_b_fraction: float = Field(default=0.30, gt=0.0, le=1.0)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @model_validator(mode="after")
    def validate_tier_fractions(self) -> "LLMConfig":
        """Enforce that tier_a and tier_b fractions leave room for tier_c."""
        if self.tier_a_fraction + self.tier_b_fraction > 1.0:
            raise ValueError(
                f"tier_a_fraction ({self.tier_a_fraction}) + tier_b_fraction ({self.tier_b_fraction}) "
                "must not exceed 1.0"
            )
        return self

    def resolve_weights(self, profile: str | None = None) -> RelevanceWeights:
        """Return the RelevanceWeights for the given profile name.

        Falls back to self.relevance_weights if the profile is None, empty,
        or not found in weight_profiles or DEFAULT_WEIGHT_PROFILES.

        Args:
            profile: Named weight profile (e.g. "investigation", "political").

        Returns:
            RelevanceWeights instance for the requested profile.
        """
        if profile:
            if profile in self.weight_profiles:
                return self.weight_profiles[profile]
            if profile in DEFAULT_WEIGHT_PROFILES:
                return RelevanceWeights(**DEFAULT_WEIGHT_PROFILES[profile])
        return self.relevance_weights
