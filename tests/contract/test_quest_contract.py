"""
test_quest_contract.py - Contract conformance tests for quest engine YAML.

Does NOT: execute quest engine runtime code.

Dependencies injected: None.
"""

from tests.contract.contract_test_support import load_contract


CONTRACT_FILE_NAME = "quest_engine.yaml"
CONTRACT_NAME = "quest_engine"
EXPECTED_AUTH_SCOPE = "graph_write"
EXPECTED_REPLAY_BEHAVIOR = "return_previous"
EXPECTED_ERROR_CODES = {"IDEMPOTENCY_KEY_REQUIRED", "IDEMPOTENCY_KEY_INVALID"}
EXPECTED_TEST_ENTRY = "test_quest_contract"


def test_quest_contract_has_expected_v14_shape() -> None:
    """Quest contract should expose required v1.4 idempotency and auth fields."""

    contract = load_contract(contract_file_name=CONTRACT_FILE_NAME)

    assert contract.name == CONTRACT_NAME
    assert contract.version.startswith("v1.4")
    assert contract.auth_scope == EXPECTED_AUTH_SCOPE
    assert contract.idempotency.key_required is True
    assert contract.idempotency.replay_behavior == EXPECTED_REPLAY_BEHAVIOR
    assert EXPECTED_ERROR_CODES.issubset(set(contract.error_contract))
    assert EXPECTED_TEST_ENTRY in contract.tests
