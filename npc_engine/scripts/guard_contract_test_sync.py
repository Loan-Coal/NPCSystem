"""
guard_contract_test_sync.py - Enforces contract-YAML to test-change synchronization in CI.

Does NOT: validate contract schema correctness.

Dependencies injected: None.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Iterable

from engines.contracts.contract_loader import load_engine_contract


CONTRACTS_PREFIX = "engines/contracts/"
CONTRACT_TESTS_PREFIX = "tests/engine_contract_tests/"
YAML_SUFFIX = ".yaml"
PYTHON_SUFFIX = ".py"
INIT_FILE_SUFFIX = "__init__.py"
PROJECT_DIR_NAME = "npc_engine"

DEFAULT_BASE_REF = "HEAD"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


@dataclass(frozen=True)
class GuardResult:
    """Result model for contract-test synchronization checks."""

    is_valid: bool
    message: str


def _normalize_path(path: str) -> str:
    """Normalize path separators for cross-platform matching."""

    return path.replace("\\", "/").strip()


def _canonical_repo_path(path: str) -> str:
    """Normalize and strip optional workspace prefix from a repository path."""

    normalized = _normalize_path(path)
    project_prefix = f"{PROJECT_DIR_NAME}/"
    if normalized.startswith(project_prefix):
        return normalized.removeprefix(project_prefix)
    return normalized


def _contains_parent_traversal(path: str) -> bool:
    """Return True when a path includes parent-directory traversal segments."""

    return ".." in PurePosixPath(path).parts


def _is_contract_yaml(path: str) -> bool:
    """Return True when path points to a contract YAML document."""

    normalized = _canonical_repo_path(path)
    if _contains_parent_traversal(path=normalized):
        return False
    return normalized.startswith(CONTRACTS_PREFIX) and normalized.endswith(YAML_SUFFIX)


def _is_contract_test(path: str) -> bool:
    """Return True when path points to a Python engine contract test file."""

    normalized = _canonical_repo_path(path)
    return (
        normalized.startswith(CONTRACT_TESTS_PREFIX)
        and normalized.endswith(PYTHON_SUFFIX)
        and not normalized.endswith(INIT_FILE_SUFFIX)
    )


def _is_invalid_contract_yaml_candidate(path: str) -> bool:
    """Return True for contract-like YAML paths that include traversal segments."""

    normalized = _canonical_repo_path(path)
    return (
        normalized.startswith(CONTRACTS_PREFIX)
        and normalized.endswith(YAML_SUFFIX)
        and _contains_parent_traversal(path=normalized)
    )


def _changed_contract_paths(changed_paths: set[str]) -> set[str]:
    """Collect canonical contract YAML paths from changed paths."""

    return {_canonical_repo_path(path) for path in changed_paths if _is_contract_yaml(path)}


def _changed_contract_test_entries(changed_paths: set[str]) -> set[str]:
    """Collect changed contract test entry names from changed test file stems."""

    return {
        Path(_canonical_repo_path(path)).stem
        for path in changed_paths
        if _is_contract_test(path)
    }


def _expected_test_entries(contract_path: str) -> set[str]:
    """Load expected test entries declared by a contract YAML file."""

    project_root = Path(__file__).resolve().parents[1]
    contracts_root = (project_root / CONTRACTS_PREFIX).resolve()
    resolved_contract_path = (project_root / contract_path).resolve()
    if contracts_root not in resolved_contract_path.parents:
        raise ValueError("contract path escapes contracts directory")

    contract = load_engine_contract(contract_path=resolved_contract_path)
    return set(contract.tests)


def evaluate_contract_test_sync(changed_paths: Iterable[str]) -> GuardResult:
    """Evaluate changed paths against the contract-test synchronization rule."""

    normalized_paths = {_normalize_path(path) for path in changed_paths if _normalize_path(path)}
    invalid_contract_candidates = {
        _canonical_repo_path(path)
        for path in normalized_paths
        if _is_invalid_contract_yaml_candidate(path)
    }
    if invalid_contract_candidates:
        return GuardResult(
            is_valid=False,
            message=(
                "invalid_contract_yaml_path:"
                f" paths={','.join(sorted(invalid_contract_candidates))}"
            ),
        )

    contract_paths = _changed_contract_paths(changed_paths=normalized_paths)
    if not contract_paths:
        return GuardResult(is_valid=True, message="no_contract_yaml_changes")

    changed_test_entries = _changed_contract_test_entries(changed_paths=normalized_paths)
    required_test_entries: set[str] = set()
    try:
        for contract_path in contract_paths:
            required_test_entries = {*required_test_entries, *_expected_test_entries(contract_path=contract_path)}
    except ValueError as error:
        return GuardResult(is_valid=False, message=f"invalid_contract_yaml_path: {error}")

    missing_test_entries = required_test_entries - changed_test_entries
    if not missing_test_entries:
        return GuardResult(is_valid=True, message="contract_yaml_and_tests_changed")

    return GuardResult(
        is_valid=False,
        message=(
            "contract_yaml_changed_without_engine_contract_test_update:"
            f" missing={','.join(sorted(missing_test_entries))}"
        ),
    )


def _changed_paths_from_git(base_ref: str) -> list[str]:
    """Read changed paths from git diff relative to the base ref."""

    command = ["git", "diff", "--name-only", base_ref]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != EXIT_SUCCESS:
        raise RuntimeError(completed.stderr.strip() or "git diff failed")
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for the guard script."""

    parser = argparse.ArgumentParser(description="Enforce contract YAML to test sync checks.")
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF, help="Git diff base ref.")
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help="Optional explicit changed path. Can be repeated.",
    )
    return parser


def main() -> int:
    """Run contract-test synchronization guard and return shell exit code."""

    args = _build_parser().parse_args()
    changed_paths = args.changed_path if args.changed_path else _changed_paths_from_git(base_ref=args.base_ref)
    result = evaluate_contract_test_sync(changed_paths=changed_paths)
    print(result.message)
    return EXIT_SUCCESS if result.is_valid else EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
