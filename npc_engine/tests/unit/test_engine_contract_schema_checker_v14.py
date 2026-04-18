"""
test_engine_contract_schema_checker_v14.py - Unit tests for engine contract schema validation.

Does NOT: execute engine runtime behavior.

Dependencies injected: tmp_path fixture.
"""

from pathlib import Path

import pytest

from engines.contracts.contract_loader import load_engine_contract, load_engine_contracts
from utils.errors import ContractValidationError


def _write_valid_contract(path: Path) -> None:
    path.write_text(
        """
name: dialogue_engine
version: v1.4.0
inputs:
  - player_input
outputs:
  - dialogue_response
side_effects:
  - relation_delta
idempotency:
  key_required: true
  replay_behavior: return_previous
auth_scope: graph_write
error_contract:
  - IDEMPOTENCY_KEY_REQUIRED
tests:
  - test_dialogue_contract
""".strip(),
        encoding="utf-8",
    )


def test_validate_engine_contract_yaml_accepts_minimal_valid_contract_document(tmp_path: Path) -> None:
    """Loader should accept a valid contract document."""

    contract_path = tmp_path / "dialogue_engine.yaml"
    _write_valid_contract(path=contract_path)

    contract = load_engine_contract(contract_path=contract_path)

    assert contract.name == "dialogue_engine"
    assert contract.idempotency.key_required is True


def test_validate_engine_contract_yaml_rejects_missing_required_top_level_keys(tmp_path: Path) -> None:
    """Loader should reject contracts missing required top-level keys."""

    contract_path = tmp_path / "invalid_contract.yaml"
    contract_path.write_text(
        """
name: dialogue_engine
version: v1.4.0
inputs:
  - player_input
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ContractValidationError):
        load_engine_contract(contract_path=contract_path)


def test_validate_engine_contract_yaml_rejects_unknown_top_level_keys(tmp_path: Path) -> None:
    """Loader should reject contracts containing unknown fields."""

    contract_path = tmp_path / "contract_with_extra.yaml"
    _write_valid_contract(path=contract_path)
    contract_path.write_text(
        f"{contract_path.read_text(encoding='utf-8')}\nextra_key: value\n",
        encoding="utf-8",
    )

    with pytest.raises(ContractValidationError):
      load_engine_contract(contract_path=contract_path)


def test_load_engine_contracts_raises_when_directory_contains_no_contracts(tmp_path: Path) -> None:
    """Directory-level loader should fail when no contract files are present."""

    with pytest.raises(ContractValidationError):
        load_engine_contracts(contracts_dir=tmp_path)


def test_validate_engine_contract_yaml_rejects_string_bool_under_strict_mode(tmp_path: Path) -> None:
    """Loader should reject quoted booleans in strict contract schema mode."""

    contract_path = tmp_path / "contract_string_bool.yaml"
    contract_path.write_text(
        """
name: dialogue_engine
version: v1.4.0
inputs:
  - player_input
outputs:
  - dialogue_response
side_effects:
  - relation_delta
idempotency:
  key_required: "true"
  replay_behavior: return_previous
auth_scope: graph_write
error_contract:
  - IDEMPOTENCY_KEY_REQUIRED
tests:
  - test_dialogue_contract
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ContractValidationError):
        load_engine_contract(contract_path=contract_path)
