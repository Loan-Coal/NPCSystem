"""
Module: test_quest_generation_engine
Layer: tests/contract
Purpose: Contract conformance tests for quest_generation_engine YAML.
Dependencies: contract_test_support.
Used by: CI via pytest.
"""

from __future__ import annotations

from tests.contract.contract_test_support import load_contract


CONTRACT_FILE_NAME = "quest_generation_engine.yaml"
CONTRACT_NAME = "quest_generation_engine"
EXPECTED_TEST_ENTRY = "test_quest_generation_engine"


def test_quest_generation_engine_contract_has_expected_shape() -> None:
    """Quest generation engine contract should expose required fields."""

    contract = load_contract(contract_file_name=CONTRACT_FILE_NAME)

    assert contract.name == CONTRACT_NAME
    assert contract.uses_llm is True
    assert EXPECTED_TEST_ENTRY in contract.tests
