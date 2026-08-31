#!/usr/bin/env python
"""
Module: check_api_stability
Layer: scripts (dev tooling)
Purpose: Fail when a /v1 API response model loses a field it had in the recorded
         baseline. Removing a field is a breaking change for every consumer already
         reading it, and the engine is being licensed as middleware — a silent removal
         is discovered by the integrator, not by us. Deliberate removals are accepted
         by re-recording the baseline with --update, which puts the break in the diff.
Counterfactual: delete an annotated field from any class in api/response_models/ or
         api/schemas.py — gate RED.
Dependencies: argparse, ast, json, pathlib, sys, pydantic
Used by: make check-api-stability, tests/unit/scripts/test_check_api_stability.py
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCAN_TARGETS: tuple[Path, ...] = (
    REPO_ROOT / "src" / "npc_engine" / "api" / "response_models",
    REPO_ROOT / "src" / "npc_engine" / "api" / "schemas.py",
)
BASELINE_PATH = Path(__file__).resolve().parent / "api_stability_baseline.json"

_BASEMODEL_NAMES: frozenset[str] = frozenset({
    "BaseModel", "FrozenDialogueModel", "FrozenApiModel",
})


class FieldDrop(BaseModel):
    """A response model class that lost one or more fields vs baseline."""

    model_config = ConfigDict(frozen=True)
    model_class: str
    source_file: str
    dropped_fields: list[str]


def _extract_model_fields(py_file: Path) -> dict[str, list[str]]:
    """Parse py_file; return {ClassName: [annotated_field_names]} for BaseModel subclasses."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return {}
    result: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {
            b.id if isinstance(b, ast.Name) else (b.attr if isinstance(b, ast.Attribute) else "")
            for b in node.bases
        }
        if not (bases & _BASEMODEL_NAMES):
            continue
        fields = [
            item.target.id
            for item in node.body
            if isinstance(item, ast.AnnAssign)
            and isinstance(item.target, ast.Name)
            and not item.target.id.startswith("_")
            and item.target.id != "model_config"
        ]
        if fields:
            result[node.name] = fields
    return result


def _rel(path: Path) -> str:
    """Repo-relative POSIX path used as a stable baseline key."""
    return path.relative_to(REPO_ROOT).as_posix()


def _scan_models() -> dict[str, dict[str, list[str]]]:
    """Return {rel_path: {ClassName: [fields]}} for all scan targets."""
    models: dict[str, dict[str, list[str]]] = {}
    for target in _SCAN_TARGETS:
        files = [target] if target.is_file() else sorted(target.rglob("*.py"))
        for py_file in files:
            if "__pycache__" in str(py_file):
                continue
            extracted = _extract_model_fields(py_file)
            if extracted:
                models[_rel(py_file)] = extracted
    return models


def _load_baseline() -> dict[str, dict[str, list[str]]]:
    """Load baseline from JSON; return empty dict if missing."""
    if not BASELINE_PATH.exists():
        return {}
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def detect_drops(
    baseline: dict[str, dict[str, list[str]]],
    current: dict[str, dict[str, list[str]]],
) -> list[FieldDrop]:
    """Return FieldDrop for every class that lost fields vs baseline."""
    drops: list[FieldDrop] = []
    for relpath, classes in baseline.items():
        for class_name, baseline_fields in classes.items():
            current_fields = set((current.get(relpath) or {}).get(class_name) or [])
            dropped = [f for f in baseline_fields if f not in current_fields]
            if dropped:
                drops.append(FieldDrop(
                    model_class=class_name,
                    source_file=relpath,
                    dropped_fields=dropped,
                ))
    return drops


def _report(drops: list[FieldDrop]) -> str:
    """Format findings as a human-readable string."""
    if not drops:
        return "check-api-stability: OK — no response model fields removed.\n"
    lines = [f"check-api-stability: {len(drops)} model(s) lost fields vs baseline:"]
    for d in drops:
        lines.append(f"  {d.source_file}::{d.model_class}  dropped: {d.dropped_fields}")
    lines.append("Removing a /v1 response field breaks consumers. If deliberate, run")
    lines.append("  python scripts/check_api_stability.py --update  (puts the break in the diff).")
    return "\n".join(lines)


def update_baseline(current: dict[str, dict[str, list[str]]]) -> None:
    """Overwrite the baseline with the current model state."""
    BASELINE_PATH.write_text(
        json.dumps(current, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"check-api-stability: baseline updated → {BASELINE_PATH}")


def main(argv: Sequence[str] | None = None) -> int:
    """Fail when an API response model drops a field it carried in the baseline."""
    parser = argparse.ArgumentParser(description="API field stability gate.")
    parser.add_argument("--update", action="store_true", help="Accept the current model shape.")
    args = parser.parse_args(argv)

    current = _scan_models()
    if args.update:
        update_baseline(current)
        return 0

    drops = detect_drops(_load_baseline(), current)
    print(_report(drops))
    if drops:
        print(f"check-api-stability: {len(drops)} field drop(s) — gate RED.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
