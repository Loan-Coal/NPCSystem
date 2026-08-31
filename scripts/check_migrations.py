#!/usr/bin/env python
"""
Module: check_migrations
Layer: scripts (dev tooling)
Purpose: Fail when a node-type YAML gains a required field that no migration claims.
         Neo4j is schemaless for properties, so the obligation a new required field
         creates is a BACKFILL of existing nodes, not a DDL change — reads break on
         nodes that predate the field. This gate makes that obligation explicit.
Contract: a migration in scripts/migrations/ claims fields with a module-level
         MIGRATES list of (node_type, field) pairs, e.g.
             MIGRATES = [("character", "voice_descriptor")]
         The list is read by AST, never imported, so the gate never executes a
         migration. scripts/node_type_snapshot.json records the accepted state;
         `--update` re-records it once the migration exists (R1.8, DEC-224).
Dependencies: argparse, ast, json, pathlib, sys, yaml, pydantic
Used by: make check-migrations, tests/unit/scripts/test_check_migrations.py
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Sequence

import yaml
from pydantic import BaseModel, ConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]
NODES_DIR = REPO_ROOT / "src" / "npc_engine" / "type_registry" / "base_nodes"
MIGRATIONS_DIR = REPO_ROOT / "scripts" / "migrations"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "node_type_snapshot.json"
DECLARATION_NAME = "MIGRATES"


class UnmigratedField(BaseModel):
    """A required field added to a node type that no migration claims."""

    model_config = ConfigDict(frozen=True)
    node_type: str
    field: str


def _load_snapshot(path: Path = SNAPSHOT_PATH) -> dict[str, list[str]]:
    """Return node_type -> accepted required field names; empty when no snapshot exists."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_node_types(nodes_dir: Path = NODES_DIR) -> dict[str, list[str]]:
    """Return node_type -> required field names, read from the base_nodes YAML registry."""
    result: dict[str, list[str]] = {}
    for yaml_file in sorted(nodes_dir.glob("*.yaml")):
        doc = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        fields = doc.get("fields") or {}
        node_type = str(doc.get("node_type", yaml_file.stem))
        result[node_type] = [n for n, meta in fields.items() if (meta or {}).get("required")]
    return result


def _declared_pairs(source: str) -> set[tuple[str, str]]:
    """Extract the MIGRATES (node_type, field) pairs from one migration's source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    pairs: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, (ast.List, ast.Tuple)):
            continue
        if not any(isinstance(t, ast.Name) and t.id == DECLARATION_NAME for t in node.targets):
            continue
        for item in node.value.elts:
            if not isinstance(item, ast.Tuple) or len(item.elts) != 2:
                continue
            a, b = item.elts
            if isinstance(a, ast.Constant) and isinstance(b, ast.Constant):
                if isinstance(a.value, str) and isinstance(b.value, str):
                    pairs.add((a.value, b.value))
    return pairs


def read_migrated_pairs(migrations_dir: Path = MIGRATIONS_DIR) -> set[tuple[str, str]]:
    """Return every (node_type, field) pair claimed by a migration in migrations_dir."""
    pairs: set[tuple[str, str]] = set()
    if not migrations_dir.exists():
        return pairs
    for py_file in sorted(migrations_dir.glob("*.py")):
        pairs |= _declared_pairs(py_file.read_text(encoding="utf-8"))
    return pairs


def detect_unmigrated(
    snapshot: dict[str, list[str]],
    current: dict[str, list[str]],
    migrated: set[tuple[str, str]],
) -> list[UnmigratedField]:
    """Return every required field added since the snapshot that no migration claims."""
    unmigrated: list[UnmigratedField] = []
    for node_type, fields in sorted(current.items()):
        accepted = set(snapshot.get(node_type, []))
        for field in fields:
            if field in accepted or (node_type, field) in migrated:
                continue
            unmigrated.append(UnmigratedField(node_type=node_type, field=field))
    return unmigrated


def format_report(unmigrated: list[UnmigratedField]) -> str:
    """Return a human-readable report naming the exact declaration each finding needs."""
    if not unmigrated:
        return "check-migrations: OK — every required field is snapshotted or migrated.\n"
    pairs = ", ".join(f'("{u.node_type}", "{u.field}")' for u in unmigrated)
    lines = [f"check-migrations: {len(unmigrated)} required field(s) with no migration:"]
    lines += [f"  {u.node_type}.{u.field}" for u in unmigrated]
    lines.append("")
    lines.append("Existing nodes in a live graph do not carry these fields. Either:")
    rel = MIGRATIONS_DIR.relative_to(REPO_ROOT).as_posix()
    lines.append(f"  1. add a backfill in {rel}/ declaring  {DECLARATION_NAME} = [{pairs}]")
    lines.append("  2. or, if no backfill is needed, record the decision with:")
    lines.append("       python scripts/check_migrations.py --update")
    return "\n".join(lines)


def update_snapshot(current: dict[str, list[str]], path: Path = SNAPSHOT_PATH) -> None:
    """Record the current required-field state as the accepted baseline."""
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"check-migrations: snapshot updated → {path}")


def main(argv: Sequence[str] | None = None) -> int:
    """Fail when a required field is added with neither a migration nor a snapshot update."""
    parser = argparse.ArgumentParser(description="Node-type migration gate.")
    parser.add_argument("--update", action="store_true", help="Accept the current state.")
    parser.add_argument("--nodes-dir", type=Path, default=NODES_DIR)
    parser.add_argument("--migrations-dir", type=Path, default=MIGRATIONS_DIR)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    args = parser.parse_args(argv)

    current = read_node_types(args.nodes_dir)
    if args.update:
        update_snapshot(current, args.snapshot)
        return 0

    unmigrated = detect_unmigrated(
        _load_snapshot(args.snapshot), current, read_migrated_pairs(args.migrations_dir)
    )
    print(format_report(unmigrated))
    return 1 if unmigrated else 0


if __name__ == "__main__":
    sys.exit(main())
