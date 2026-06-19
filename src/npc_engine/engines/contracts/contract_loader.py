"""
contract_loader.py - Loads and validates engine contract YAML files.
Layer: engines
Purpose: Loads and validates engine contract YAML files.

Does NOT: enforce contracts at runtime.

Dependencies injected: None.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.engines.contracts.contract_models import EngineContract
from npc_engine.utils.errors import ContractValidationError


CONTRACT_GLOB_PATTERN = "*.yaml"


def _read_contract_document(contract_path: Path) -> dict[str, Any]:
    """Read one contract YAML file into a validated mapping payload."""

    if not contract_path.exists():
        raise ContractValidationError(contract_path=str(contract_path), detail="contract file does not exist")

    try:
        return load_yaml_mapping(path=contract_path, root_error_message="contract root must be a YAML object")
    except (OSError, UnicodeError) as error:
        raise ContractValidationError(contract_path=str(contract_path), detail=str(error)) from error
    except (ValueError, yaml.YAMLError) as error:
        raise ContractValidationError(contract_path=str(contract_path), detail=str(error)) from error


def load_engine_contract(contract_path: Path) -> EngineContract:
    """Load one YAML contract file into a typed engine contract model."""

    payload = _read_contract_document(contract_path=contract_path)
    try:
        return EngineContract.model_validate(payload)
    except ValidationError as error:
        raise ContractValidationError(contract_path=str(contract_path), detail=str(error)) from error


def load_engine_contracts(contracts_dir: Path) -> list[EngineContract]:
    """Load all engine contracts from a directory in deterministic order."""

    if not contracts_dir.exists():
        raise ContractValidationError(
            contract_path=str(contracts_dir),
            detail="contracts directory does not exist",
        )

    paths = sorted(contracts_dir.glob(CONTRACT_GLOB_PATTERN))
    if not paths:
        raise ContractValidationError(
            contract_path=str(contracts_dir),
            detail="no contract files found",
        )

    return [load_engine_contract(contract_path=path) for path in paths]
