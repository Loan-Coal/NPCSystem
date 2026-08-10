"""
Module: tests.integration.evals.conftest
Layer: tests
Purpose: Fixtures for the committed k3_73e6c36 eval artifact used by integration tests.
         Points to repo-relative paths; does not call LLMs, Neo4j, or any runtime service.
Dependencies: json, pathlib, pytest
Used by: test_real_artifact_invariants.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ARTIFACT_DIR = _REPO_ROOT / "evals" / "generations" / "k3_73e6c36"
_LABELS_FILE = _REPO_ROOT / "evals" / "calibration" / "labels_v1.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file, skipping blank lines."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


@pytest.fixture(scope="session")
def artifact_dir() -> Path:
    """Path to the committed k3_73e6c36 generation directory."""
    return _ARTIFACT_DIR


@pytest.fixture(scope="session")
def artifact_meta(artifact_dir: Path) -> dict[str, Any]:
    """Parsed meta.json from the committed artifact."""
    return json.loads((artifact_dir / "meta.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def k_value(artifact_meta: dict[str, Any]) -> int:
    """Repetition count (k) from the committed artifact's meta.json."""
    return int(artifact_meta["k"])


@pytest.fixture(scope="session")
def outputs(artifact_dir: Path) -> list[dict[str, Any]]:
    """All rows from outputs.jsonl in the committed artifact."""
    return _read_jsonl(artifact_dir / "outputs.jsonl")


@pytest.fixture(scope="session")
def judged(artifact_dir: Path) -> list[dict[str, Any]]:
    """All rows from judged.jsonl in the committed artifact."""
    return _read_jsonl(artifact_dir / "judged.jsonl")


@pytest.fixture(scope="session")
def det_judged(artifact_dir: Path) -> list[dict[str, Any]]:
    """All rows from deterministic_judged.jsonl in the committed artifact."""
    return _read_jsonl(artifact_dir / "deterministic_judged.jsonl")


@pytest.fixture(scope="session")
def labels() -> list[dict[str, Any]]:
    """All rows from labels_v1.jsonl (human calibration labels)."""
    return _read_jsonl(_LABELS_FILE)
