"""
test_llm_config.py - Unit tests for LLM config models and loader.

Does NOT: test runtime prompt or LLM adapter behavior.

Dependencies injected: tmp_path fixture.
"""

from pathlib import Path

import pytest

from npc_engine.schema.context_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens
from npc_engine.utils.errors import LLMConfigMisconfiguredError, LLMConfigValidationError


# ── Helpers ──────────────────────────────────────────────────────────────────

_VALID_YAML = """
prompt_schema_version: "1.4"
compression_prompt_version: "1.0"
tier_budget_tokens:
  tier_a: 200
  tier_b: 300
  tier_c: 100
session_turns_budget_tokens: 400
compression_trigger_ratio: 0.8
max_proximity_hops: 2
relevance_weights:
  recency: 0.2
  severity: 0.2
  proximity: 0.2
  relation: 0.2
  quest: 0.2
""".strip()


def _valid_weights() -> dict:
    return dict(recency=0.2, severity=0.2, proximity=0.2, relation=0.2, quest=0.2)


# ── RelevanceWeights.validate_weights_sum ────────────────────────────────────


def test_relevance_weights_accepts_sum_of_one() -> None:
    """Weights that sum exactly to 1.0 should be accepted."""

    weights = RelevanceWeights(**_valid_weights())
    assert abs(sum(vars(weights).values()) - 1.0) < 1e-6


def test_relevance_weights_rejects_sum_not_one() -> None:
    """Weights whose sum deviates from 1.0 should raise ValueError."""

    bad = _valid_weights()
    bad["recency"] = 0.5

    with pytest.raises(ValueError, match="sum to 1.0"):
        RelevanceWeights(**bad)


def test_relevance_weights_is_frozen() -> None:
    """RelevanceWeights should be immutable after construction."""

    weights = RelevanceWeights(**_valid_weights())

    with pytest.raises(Exception):
        weights.recency = 0.9  # type: ignore[misc]


# ── LLMConfig model ──────────────────────────────────────────────────────────


def test_llm_config_rejects_zero_tier_budget() -> None:
    """TierBudgetTokens fields must be > 0."""

    with pytest.raises(ValueError):
        TierBudgetTokens(tier_a=0, tier_b=100, tier_c=50)


def test_llm_config_rejects_extra_fields() -> None:
    """LLMConfig uses extra='forbid' — unknown fields must raise."""

    with pytest.raises(Exception):
        LLMConfig(
            prompt_schema_version="1.4",
            compression_prompt_version="1.0",
            tier_budget_tokens=TierBudgetTokens(tier_a=100, tier_b=200, tier_c=50),
            session_turns_budget_tokens=400,
            compression_trigger_ratio=0.8,
            max_proximity_hops=2,
            relevance_weights=RelevanceWeights(**_valid_weights()),
            unknown_field="oops",  # type: ignore[call-arg]
        )


# ── load_llm_config ──────────────────────────────────────────────────────────


def test_load_llm_config_parses_valid_file(tmp_path: Path) -> None:
    """A valid llm_config YAML should be parsed into an LLMConfig instance."""

    from npc_engine.schema.llm_schema_loader import load_llm_config

    config_path = tmp_path / "llm_config.yaml"
    config_path.write_text(_VALID_YAML, encoding="utf-8")

    config = load_llm_config(config_path=str(config_path))

    assert config.prompt_schema_version == "1.4"
    assert config.tier_budget_tokens.tier_a == 200
    assert config.max_proximity_hops == 2


def test_load_llm_config_raises_when_file_missing(tmp_path: Path) -> None:
    """A missing config file should raise LLMConfigMisconfiguredError."""

    from npc_engine.schema.llm_schema_loader import load_llm_config

    with pytest.raises(LLMConfigMisconfiguredError):
        load_llm_config(config_path=str(tmp_path / "nonexistent.yaml"))


def test_load_llm_config_raises_validation_error_for_list_root(tmp_path: Path) -> None:
    """A config YAML whose root is a list should raise LLMConfigValidationError."""

    from npc_engine.schema.llm_schema_loader import load_llm_config

    config_path = tmp_path / "bad.yaml"
    config_path.write_text("- item1\n", encoding="utf-8")

    with pytest.raises(LLMConfigValidationError):
        load_llm_config(config_path=str(config_path))


def test_load_llm_config_raises_validation_error_for_bad_weights(tmp_path: Path) -> None:
    """A config where weights do not sum to 1.0 should raise LLMConfigValidationError."""

    from npc_engine.schema.llm_schema_loader import load_llm_config

    bad_yaml = _VALID_YAML.replace("recency: 0.2", "recency: 0.9")
    config_path = tmp_path / "bad_weights.yaml"
    config_path.write_text(bad_yaml, encoding="utf-8")

    with pytest.raises(LLMConfigValidationError):
        load_llm_config(config_path=str(config_path))
