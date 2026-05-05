"""
check_contracts.py - CLI utility to validate engine contract YAML files.

Does NOT: execute any engine behavior.

Dependencies injected: None.
"""

from __future__ import annotations

import logging
from pathlib import Path

from npc_engine.engines.contracts.contract_loader import load_engine_contracts
from npc_engine.utils.errors import ContractValidationError


LOGGER_NAME = "contract_checker"
DEFAULT_CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "engines" / "contracts"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def validate_contracts(contracts_dir: Path) -> int:
    """Validate all contracts in the given directory and return process exit code."""

    logger = logging.getLogger(LOGGER_NAME)
    try:
        contracts = load_engine_contracts(contracts_dir=contracts_dir)
    except ContractValidationError as error:
        logger.error("contract_validation_failed", extra={"error": str(error)})
        return EXIT_FAILURE

    logger.info("contract_validation_passed", extra={"count": len(contracts)})
    return EXIT_SUCCESS


def main() -> int:
    """Run contract validation for the default contracts directory."""

    logging.basicConfig(level=logging.INFO)
    return validate_contracts(contracts_dir=DEFAULT_CONTRACTS_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
