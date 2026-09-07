"""
test_run_config_effective_temperature.py - A run must record the temperature it actually
ran at, not the one its config file declares.

Why this exists: dialogue's llm_config.yaml declares temperature 0.15, but the structured
path -- the only path dialogue uses -- runs at STRUCTURED_OUTPUT_TEMPERATURE, because
LLMStructuredProtocol.generate_structured takes no temperature argument at all and the
adapter substitutes the setting. Every run therefore recorded 0.15 as its provenance while
the model ran at 0.1, and DEC-176 leans on the recorded figure ("the report states
temperature=0.15"). Provenance means what ran.

Does NOT: call an LLM, or assert generation behaviour.

Dependencies injected: None.
"""

from __future__ import annotations

from engine_adapter import structured_output_temperature
from run_config import effective_generation_temperature


def test_the_structured_temperature_is_read_from_the_engine_not_guessed() -> None:
    """The gateway reads the shipped setting, so the record cannot drift from the engine."""
    assert structured_output_temperature() == 0.1


def test_the_effective_temperature_is_the_structured_one_not_the_yaml_one() -> None:
    """Dialogue only ever calls generate_structured, so the YAML value never reaches it."""
    assert effective_generation_temperature(configured=0.15) == structured_output_temperature()


def test_a_configured_value_equal_to_the_structured_one_is_unchanged() -> None:
    """No special-casing: the function reports what runs, whatever the config says."""
    assert effective_generation_temperature(configured=0.1) == 0.1
