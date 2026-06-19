"""
check_contracts.py - CLI utility to validate engine contract YAML files.
Layer: unknown
Purpose: CLI utility to validate engine contract YAML files.

Does NOT: execute any engine behavior.

Dependencies injected: None.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from npc_engine.engines.contracts.contract_loader import load_engine_contracts
from npc_engine.utils.errors import ContractValidationError


LOGGER_NAME = "contract_checker"
DEFAULT_CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "engines" / "contracts"
# File lives at: src/npc_engine/scripts/<file>.py  →  parents[3] = repo root.
DEFAULT_TESTS_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_TESTS_SUBDIR = "tests" / Path("contract")
PYTHON_SUFFIX = ".py"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def _resolve_test_path(tests_root: Path, stem: str) -> Path:
    """Return the expected absolute path for a contract test file stem."""
    return tests_root / CONTRACT_TESTS_SUBDIR / f"{stem}{PYTHON_SUFFIX}"


def _check_test_paths_exist(contracts_dir: Path, tests_root: Path, logger: logging.Logger) -> list[str]:
    """Return a list of error strings for any missing declared test file paths."""
    try:
        contracts = load_engine_contracts(contracts_dir=contracts_dir)
    except ContractValidationError:
        return []  # Schema errors are reported by the caller

    errors: list[str] = []
    for contract in contracts:
        for stem in contract.tests:
            test_path = _resolve_test_path(tests_root=tests_root, stem=stem)
            if not test_path.exists():
                logger.error(
                    "contract_test_file_missing",
                    extra={"contract": contract.name, "path": str(test_path)},
                )
                errors.append(f"  {contract.name}: tests path not found: {test_path}")
    return errors


def validate_contracts(contracts_dir: Path, tests_root: Path | None = None) -> int:
    """Validate all contracts in the given directory and return process exit code.

    Args:
        contracts_dir: Directory containing contract YAML files.
        tests_root: Root of the repository used to resolve declared test paths.
                    Defaults to the repository root derived from this file's location.
    Returns:
        EXIT_SUCCESS (0) if all contracts are valid and all test paths exist.
        EXIT_FAILURE (1) if any contract is invalid or a declared test path is missing.
    """
    resolved_tests_root = tests_root if tests_root is not None else DEFAULT_TESTS_ROOT
    logger = logging.getLogger(LOGGER_NAME)
    try:
        contracts = load_engine_contracts(contracts_dir=contracts_dir)
    except ContractValidationError as error:
        logger.error("contract_validation_failed", extra={"error": str(error)})
        return EXIT_FAILURE

    path_errors = _check_test_paths_exist(
        contracts_dir=contracts_dir,
        tests_root=resolved_tests_root,
        logger=logger,
    )
    if path_errors:
        for error_line in path_errors:
            logger.error("contract_test_path_error", extra={"detail": error_line})
        sys.stdout.write("\n".join(path_errors) + "\n")
        return EXIT_FAILURE

    logger.info("contract_validation_passed", extra={"count": len(contracts)})
    return EXIT_SUCCESS


def main() -> int:
    """Run contract validation for the default contracts directory."""

    logging.basicConfig(level=logging.INFO)
    return validate_contracts(contracts_dir=DEFAULT_CONTRACTS_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
