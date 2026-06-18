"""
Module: test_contract_guards_sev43
Layer: tests/unit
Purpose: Regression tests for SEV-43 contract guard hardening (disk existence + symbol checks).
Dependencies: check_contracts, guard_contract_test_sync, tmp_path fixture.
Used by: CI via pytest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from npc_engine.scripts.check_contracts import validate_contracts
from npc_engine.scripts.guard_contract_test_sync import evaluate_contract_test_sync


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_CONTRACT_YAML_TEMPLATE = """
name: demo_engine
version: v1.0.0
uses_llm: false
inputs:
  - some_input
outputs:
  - some_output
side_effects:
  - none
idempotency:
  key_required: true
  replay_behavior: return_previous
auth_scope: graph_write
error_contract:
  - SOME_ERROR
tests:
  - {tests_entry}
""".strip()


def _write_contract(contracts_dir: Path, stem: str = "demo_engine", tests_entry: str = "test_demo_engine") -> Path:
    """Write a minimal valid contract YAML and return its path."""
    yaml_content = _VALID_CONTRACT_YAML_TEMPLATE.format(tests_entry=tests_entry)
    contracts_dir.mkdir(parents=True, exist_ok=True)
    path = contracts_dir / f"{stem}.yaml"
    path.write_text(yaml_content, encoding="utf-8")
    return path


def _write_test_file(tests_contract_dir: Path, stem: str, contract_name: str) -> Path:
    """Write a minimal test file that references the given contract name."""
    tests_contract_dir.mkdir(parents=True, exist_ok=True)
    path = tests_contract_dir / f"{stem}.py"
    path.write_text(
        f"# contract: {contract_name}\ndef test_placeholder() -> None:\n    pass\n",
        encoding="utf-8",
    )
    return path


def _make_project_root(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a minimal fake project root and return (project_root, contracts_dir, tests_contract_dir)."""
    contracts_dir = tmp_path / "src" / "npc_engine" / "engines" / "contracts"
    contracts_dir.mkdir(parents=True)
    tests_contract_dir = tmp_path / "tests" / "contract"
    tests_contract_dir.mkdir(parents=True)
    return tmp_path, contracts_dir, tests_contract_dir


# ---------------------------------------------------------------------------
# check_contracts — test path existence
# ---------------------------------------------------------------------------


class TestCheckContractsMissingTestFile:
    """check_contracts exits 1 when a contract's tests: entry has no matching file on disk."""

    def test_missing_test_file_returns_failure(self, tmp_path: Path) -> None:
        """validate_contracts should return EXIT_FAILURE when declared test file is absent."""
        contracts_dir = tmp_path / "contracts"
        contracts_dir.mkdir()
        _write_contract(contracts_dir, tests_entry="test_nonexistent_file")
        # No test file written — the path does not exist

        result = validate_contracts(contracts_dir=contracts_dir, tests_root=tmp_path)

        assert result != 0, "Expected exit 1 when declared test path is missing from disk"

    def test_missing_test_file_message_contains_path(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """validate_contracts error output should include the missing test path."""
        contracts_dir = tmp_path / "contracts"
        contracts_dir.mkdir()
        _write_contract(contracts_dir, tests_entry="test_nonexistent_file")

        validate_contracts(contracts_dir=contracts_dir, tests_root=tmp_path)

        captured = capsys.readouterr()
        assert "test_nonexistent_file" in (captured.out + captured.err)


class TestCheckContractsValidContract:
    """check_contracts exits 0 when contract and test file are both present."""

    def test_valid_contract_with_existing_test_returns_success(self, tmp_path: Path) -> None:
        """validate_contracts should return EXIT_SUCCESS when all declared test files exist."""
        contracts_dir = tmp_path / "contracts"
        contracts_dir.mkdir()
        tests_contract_dir = tmp_path / "tests" / "contract"
        _write_contract(contracts_dir, tests_entry="test_demo_engine")
        _write_test_file(tests_contract_dir, stem="test_demo_engine", contract_name="demo_engine")

        result = validate_contracts(contracts_dir=contracts_dir, tests_root=tmp_path)

        assert result == 0, "Expected exit 0 for valid contract + existing test file"


# ---------------------------------------------------------------------------
# guard_contract_test_sync — file existence + symbol check
# ---------------------------------------------------------------------------


class TestSyncGuardMissingTestFile:
    """evaluate_contract_test_sync fails when the declared test file does not exist on disk."""

    def test_sync_guard_fails_when_test_file_absent(self, tmp_path: Path) -> None:
        """Sync guard should return is_valid=False when a contract's declared test file is missing."""
        project_root, contracts_dir, _tests_dir = _make_project_root(tmp_path)
        _write_contract(contracts_dir, stem="demo_engine", tests_entry="test_demo_engine")
        # No test file written

        result = evaluate_contract_test_sync(
            changed_paths=["engines/contracts/demo_engine.yaml"],
            project_root=project_root,
        )

        assert result.is_valid is False
        assert "test_demo_engine" in result.message

    def test_sync_guard_message_contains_stem_when_file_absent(self, tmp_path: Path) -> None:
        """Sync guard failure message should include the missing stem."""
        project_root, contracts_dir, _tests_dir = _make_project_root(tmp_path)
        _write_contract(contracts_dir, stem="demo_engine", tests_entry="test_demo_engine")

        result = evaluate_contract_test_sync(
            changed_paths=["engines/contracts/demo_engine.yaml"],
            project_root=project_root,
        )

        assert "test_demo_engine" in result.message


class TestSyncGuardMissingSymbol:
    """evaluate_contract_test_sync fails when test file exists but does not reference contract name."""

    def test_sync_guard_fails_when_symbol_absent(self, tmp_path: Path) -> None:
        """Sync guard should return is_valid=False when test file omits the contract name."""
        project_root, contracts_dir, tests_dir = _make_project_root(tmp_path)
        _write_contract(contracts_dir, stem="demo_engine", tests_entry="test_demo_engine")
        # Test file exists but does NOT mention the contract name
        test_file = tests_dir / "test_demo_engine.py"
        test_file.write_text("def test_something() -> None:\n    pass\n", encoding="utf-8")

        result = evaluate_contract_test_sync(
            changed_paths=["engines/contracts/demo_engine.yaml"],
            project_root=project_root,
        )

        assert result.is_valid is False
        assert "demo_engine" in result.message


class TestSyncGuardValidContractWithSymbol:
    """evaluate_contract_test_sync passes when test file exists and references contract name."""

    def test_sync_guard_passes_when_file_exists_and_has_symbol(self, tmp_path: Path) -> None:
        """Sync guard should return is_valid=True for well-formed contract + matching test."""
        project_root, contracts_dir, tests_dir = _make_project_root(tmp_path)
        _write_contract(contracts_dir, stem="demo_engine", tests_entry="test_demo_engine")
        _write_test_file(tests_dir, stem="test_demo_engine", contract_name="demo_engine")

        # Also provide the test file in the diff so the sync check passes
        result = evaluate_contract_test_sync(
            changed_paths=[
                "engines/contracts/demo_engine.yaml",
                "tests/engine_contract_tests/test_demo_engine.py",
            ],
            project_root=project_root,
        )

        assert result.is_valid is True
