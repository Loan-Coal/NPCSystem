"""
Module: tests.unit.scripts.test_check_migrations
Layer: tests
Purpose: Unit tests for scripts/check_migrations.py — pins the R1.8 counterfactual
         (a required field with no migration reds, the same field with a declaring
         migration greens) and the MIGRATES declaration parser.
Dependencies: pathlib, sys, pytest, check_migrations
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_migrations import (  # noqa: E402
    UnmigratedField,
    detect_unmigrated,
    format_report,
    main,
    read_migrated_pairs,
    read_node_types,
    _declared_pairs,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _world(tmp_path: Path, yaml_text: str, migration_text: str | None = None) -> dict[str, Path]:
    """Build a throwaway nodes dir, migrations dir and snapshot path."""
    nodes = tmp_path / "base_nodes"
    nodes.mkdir()
    (nodes / "character.yaml").write_text(yaml_text, encoding="utf-8")
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    if migration_text is not None:
        (migrations / "add_thing.py").write_text(migration_text, encoding="utf-8")
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({"character": ["id"]}), encoding="utf-8")
    return {"nodes": nodes, "migrations": migrations, "snapshot": snapshot}


_YAML_ONE_FIELD = "node_type: character\nfields:\n  id: { type: str, required: true }\n"
_YAML_TWO_FIELDS = _YAML_ONE_FIELD + "  voice: { type: str, required: true }\n"


def _argv(w: dict[str, Path]) -> list[str]:
    """Build the CLI argv that points main() at the throwaway world."""
    return [
        "--nodes-dir", str(w["nodes"]),
        "--migrations-dir", str(w["migrations"]),
        "--snapshot", str(w["snapshot"]),
    ]


# --- the R1.8 counterfactual, both directions ------------------------------


def test_new_required_field_without_a_migration_reds(tmp_path: Path) -> None:
    w = _world(tmp_path, _YAML_TWO_FIELDS)
    assert main(_argv(w)) == 1


def test_new_required_field_with_a_declaring_migration_greens(tmp_path: Path) -> None:
    w = _world(tmp_path, _YAML_TWO_FIELDS, 'MIGRATES = [("character", "voice")]\n')
    assert main(_argv(w)) == 0


def test_unchanged_registry_greens(tmp_path: Path) -> None:
    w = _world(tmp_path, _YAML_ONE_FIELD)
    assert main(_argv(w)) == 0


def test_update_accepts_the_current_state(tmp_path: Path) -> None:
    w = _world(tmp_path, _YAML_TWO_FIELDS)
    assert main(_argv(w) + ["--update"]) == 0
    assert main(_argv(w)) == 0


# --- component behaviour ---------------------------------------------------


def test_optional_fields_are_not_tracked(tmp_path: Path) -> None:
    yaml_text = _YAML_ONE_FIELD + "  nickname: { type: str, required: false }\n"
    w = _world(tmp_path, yaml_text)
    assert main(_argv(w)) == 0


def test_a_migration_for_a_different_field_does_not_satisfy_the_gate(tmp_path: Path) -> None:
    w = _world(tmp_path, _YAML_TWO_FIELDS, 'MIGRATES = [("character", "something_else")]\n')
    assert main(_argv(w)) == 1


def test_declared_pairs_reads_the_migrates_list() -> None:
    src = 'X = 1\nMIGRATES = [("character", "voice"), ("quest", "tier")]\n'
    assert _declared_pairs(src) == {("character", "voice"), ("quest", "tier")}


def test_declared_pairs_ignores_other_assignments_and_bad_shapes() -> None:
    assert _declared_pairs('OTHER = [("a", "b")]\n') == set()
    assert _declared_pairs('MIGRATES = [("a",), "b", (1, 2)]\n') == set()


def test_declared_pairs_survives_an_unparseable_migration() -> None:
    assert _declared_pairs("def broken(:\n") == set()


def test_read_migrated_pairs_never_imports_the_migration(tmp_path: Path) -> None:
    """A migration with an import-time side effect must not run during the scan."""
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    sentinel = tmp_path / "ran.txt"
    (migrations / "m.py").write_text(
        f'import pathlib\npathlib.Path(r"{sentinel}").write_text("ran")\n'
        'MIGRATES = [("character", "voice")]\n',
        encoding="utf-8",
    )
    assert read_migrated_pairs(migrations) == {("character", "voice")}
    assert not sentinel.exists()


def test_report_names_the_declaration_the_finding_needs() -> None:
    report = format_report([UnmigratedField(node_type="character", field="voice")])
    assert 'MIGRATES = [("character", "voice")]' in report
    assert "scripts/migrations/" in report


def test_report_is_quiet_when_clean() -> None:
    assert "OK" in format_report([])


def test_detect_unmigrated_accepts_snapshotted_fields() -> None:
    found = detect_unmigrated({"character": ["id"]}, {"character": ["id"]}, set())
    assert found == []


# --- the shipped registry stays green --------------------------------------


def test_the_real_registry_is_green() -> None:
    assert main([]) == 0


def test_the_real_registry_snapshot_covers_every_node_type() -> None:
    snapshot = json.loads(
        (_REPO_ROOT / "scripts" / "node_type_snapshot.json").read_text(encoding="utf-8")
    )
    assert set(read_node_types()) == set(snapshot)
