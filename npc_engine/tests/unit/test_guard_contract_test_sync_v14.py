"""
test_guard_contract_test_sync_v14.py - Tests the contract YAML and test sync CI guard.

Does NOT: call git or mutate repository state.

Dependencies injected: None.
"""

from scripts.guard_contract_test_sync import evaluate_contract_test_sync


CONTRACT_PATH = "engines/contracts/dialogue_engine.yaml"
CONTRACT_TEST_PATH = "tests/engine_contract_tests/test_dialogue_contract.py"
QUEST_CONTRACT_PATH = "engines/contracts/quest_engine.yaml"
QUEST_CONTRACT_TEST_PATH = "tests/engine_contract_tests/test_quest_contract.py"
PREFIXED_CONTRACT_PATH = "npc_engine/engines/contracts/dialogue_engine.yaml"
PREFIXED_CONTRACT_TEST_PATH = "npc_engine/tests/engine_contract_tests/test_dialogue_contract.py"
TRAVERSAL_CONTRACT_PATH = "engines/contracts/../../tmp/escape.yaml"
UNRELATED_PATH = "engines/dialogue/context_relevance_engine.py"
EXPECTED_FAILURE_PREFIX = "contract_yaml_changed_without_engine_contract_test_update"
EXPECTED_INVALID_PATH_PREFIX = "invalid_contract_yaml_path"


def test_guard_allows_changes_when_no_contract_yaml_is_touched() -> None:
    """Guard should pass when contract YAML files are unchanged."""

    result = evaluate_contract_test_sync(changed_paths=[UNRELATED_PATH])

    assert result.is_valid is True


def test_guard_rejects_contract_yaml_change_without_contract_test_update() -> None:
    """Guard should fail when contract YAML changes without contract-test changes."""

    result = evaluate_contract_test_sync(changed_paths=[CONTRACT_PATH])

    assert result.is_valid is False
    assert result.message.startswith(EXPECTED_FAILURE_PREFIX)


def test_guard_accepts_contract_yaml_change_with_contract_test_update() -> None:
    """Guard should pass when contract YAML and contract-test files change together."""

    result = evaluate_contract_test_sync(
        changed_paths=[
            CONTRACT_PATH,
            CONTRACT_TEST_PATH,
        ]
    )

    assert result.is_valid is True


def test_guard_accepts_ci_prefixed_paths_for_contract_and_test_updates() -> None:
    """Guard should normalize CI-style prefixed paths before matching rules."""

    result = evaluate_contract_test_sync(
        changed_paths=[
            PREFIXED_CONTRACT_PATH,
            PREFIXED_CONTRACT_TEST_PATH,
        ]
    )

    assert result.is_valid is True


def test_guard_rejects_mismatched_contract_and_test_pair() -> None:
    """Guard should fail when a changed contract lacks its own test update."""

    result = evaluate_contract_test_sync(
        changed_paths=[
            QUEST_CONTRACT_PATH,
            CONTRACT_TEST_PATH,
        ]
    )

    assert result.is_valid is False
    assert result.message.startswith(EXPECTED_FAILURE_PREFIX)


def test_guard_accepts_matching_contract_specific_test_pair() -> None:
    """Guard should pass when changed contract includes its declared test file update."""

    result = evaluate_contract_test_sync(
        changed_paths=[
            QUEST_CONTRACT_PATH,
            QUEST_CONTRACT_TEST_PATH,
        ]
    )

    assert result.is_valid is True


def test_guard_rejects_traversal_contract_path_candidate() -> None:
    """Guard should fail fast when a changed contract path attempts traversal."""

    result = evaluate_contract_test_sync(changed_paths=[TRAVERSAL_CONTRACT_PATH])

    assert result.is_valid is False
    assert result.message.startswith(EXPECTED_INVALID_PATH_PREFIX)
