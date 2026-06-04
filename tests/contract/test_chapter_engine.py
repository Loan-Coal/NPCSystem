"""
Module: test_chapter_engine
Layer: tests/contract
Purpose: Contract conformance tests for chapter_engine YAML.
Dependencies: contract_test_support.
Used by: CI via pytest.
"""

from __future__ import annotations

from tests.contract.contract_test_support import load_contract


CONTRACT_FILE_NAME = "chapter_engine.yaml"
CONTRACT_NAME = "chapter_engine"
EXPECTED_TEST_ENTRY = "test_chapter_engine"


def test_chapter_engine_contract_has_expected_shape() -> None:
    """Chapter engine contract should expose required fields."""

    contract = load_contract(contract_file_name=CONTRACT_FILE_NAME)

    assert contract.name == CONTRACT_NAME
    assert contract.uses_llm is True
    assert EXPECTED_TEST_ENTRY in contract.tests
