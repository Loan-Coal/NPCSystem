"""
Module: tests.unit.scripts.test_check_api_stability
Layer: tests
Purpose: Unit tests for scripts/check_api_stability.py — pins the R1.8 counterfactual
         (a /v1 response model that loses a field reds) and the AST field extractor
         that feeds it.
Dependencies: json, pathlib, sys, pytest, check_api_stability
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_api_stability import (  # noqa: E402
    _extract_model_fields,
    _report,
    _scan_models,
    detect_drops,
    main,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

_BASELINE = {"src/api/schemas.py": {"NPCState": ["id", "name", "mood"]}}


def _model_file(tmp_path: Path, body: str) -> Path:
    """Write a throwaway module containing model definitions."""
    path = tmp_path / "models.py"
    path.write_text(body, encoding="utf-8")
    return path


# --- the R1.8 counterfactual ------------------------------------------------


def test_a_dropped_field_is_detected() -> None:
    current = {"src/api/schemas.py": {"NPCState": ["id", "name"]}}
    drops = detect_drops(_BASELINE, current)
    assert [d.dropped_fields for d in drops] == [["mood"]]


def test_an_unchanged_model_is_clean() -> None:
    assert detect_drops(_BASELINE, _BASELINE) == []


def test_an_added_field_is_not_a_drop() -> None:
    current = {"src/api/schemas.py": {"NPCState": ["id", "name", "mood", "tick"]}}
    assert detect_drops(_BASELINE, current) == []


def test_a_deleted_class_drops_all_of_its_fields() -> None:
    drops = detect_drops(_BASELINE, {"src/api/schemas.py": {}})
    assert drops[0].dropped_fields == ["id", "name", "mood"]


def test_a_deleted_file_drops_all_of_its_fields() -> None:
    drops = detect_drops(_BASELINE, {})
    assert drops[0].dropped_fields == ["id", "name", "mood"]


def test_report_points_at_the_update_escape_hatch() -> None:
    report = _report(detect_drops(_BASELINE, {"src/api/schemas.py": {"NPCState": ["id"]}}))
    assert "--update" in report


def test_report_is_quiet_when_clean() -> None:
    assert "OK" in _report([])


# --- the AST field extractor ------------------------------------------------


def test_annotated_fields_of_a_basemodel_are_extracted(tmp_path: Path) -> None:
    path = _model_file(tmp_path, "class Thing(BaseModel):\n    id: str\n    name: str | None\n")
    assert _extract_model_fields(path) == {"Thing": ["id", "name"]}


def test_non_basemodel_classes_are_ignored(tmp_path: Path) -> None:
    path = _model_file(tmp_path, "class Thing:\n    id: str\n")
    assert _extract_model_fields(path) == {}


def test_model_config_and_privates_are_not_fields(tmp_path: Path) -> None:
    body = "class Thing(BaseModel):\n    model_config: dict = {}\n    _x: int = 1\n    id: str\n"
    assert _extract_model_fields(_model_file(tmp_path, body)) == {"Thing": ["id"]}


def test_frozen_api_model_subclasses_are_scanned(tmp_path: Path) -> None:
    path = _model_file(tmp_path, "class Thing(FrozenApiModel):\n    id: str\n")
    assert _extract_model_fields(path) == {"Thing": ["id"]}


def test_an_unparseable_module_is_skipped_not_crashed(tmp_path: Path) -> None:
    assert _extract_model_fields(_model_file(tmp_path, "class Broken(:\n")) == {}


# --- the shipped API stays green -------------------------------------------


def test_the_real_api_is_green() -> None:
    assert main([]) == 0


def test_the_baseline_matches_the_shipped_models() -> None:
    """A drifted baseline would green the gate for reasons unrelated to stability."""
    recorded = json.loads(
        (_REPO_ROOT / "scripts" / "api_stability_baseline.json").read_text(encoding="utf-8")
    )
    assert _scan_models() == recorded


def test_the_baseline_is_not_empty() -> None:
    """An empty baseline would make every drop invisible."""
    assert sum(len(v) for v in json.loads(
        (_REPO_ROOT / "scripts" / "api_stability_baseline.json").read_text(encoding="utf-8")
    ).values()) > 0
