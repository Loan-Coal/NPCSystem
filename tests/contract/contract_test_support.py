"""
contract_test_support.py - Shared contract-loader helpers for engine contract tests.

Does NOT: validate runtime engine behavior.

Dependencies injected: None.
"""

from pathlib import Path

from npc_engine.engines.contracts.contract_loader import load_engine_contract
from npc_engine.engines.contracts.contract_models import EngineContract


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = PROJECT_ROOT / "src" / "npc_engine" / "engines" / "contracts"


def load_contract(contract_file_name: str) -> EngineContract:
    """Load one contract YAML document by file name."""

    contract_path = CONTRACTS_DIR / contract_file_name
    return load_engine_contract(contract_path=contract_path)
