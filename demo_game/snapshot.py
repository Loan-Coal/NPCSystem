"""
Module: snapshot
Layer: demo_game (standalone CLI tool — no engine layer imports)
Purpose: Export and restore Neo4j graph state for demo resets between takes.
Dependencies: neo4j (sync driver), json, pathlib, argparse, os, demo_game.restore_guard
Used by: Makefile targets demo-snapshot, demo-restore and eval-world-snapshot
Public surface: do_snapshot, do_restore, and the re-exported
               DERIVED_NODE_FIELDS / strip_derived_fields (DEC-211 Decision 3).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase, Driver

from demo_game.derived_fields import DERIVED_NODE_FIELDS, strip_derived_fields
from demo_game.restore_guard import (
    REMEDY_HINT,
    LiveWriterDetectedError,
    assert_no_live_writer,
    probe_seconds,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SNAPSHOT_PATH = Path(".cache/demo/snapshot.json")

NEO4J_URI_DEFAULT = "bolt://localhost:7687"
NEO4J_USER_DEFAULT = "neo4j"
NEO4J_PASSWORD_DEFAULT = "password"

_SNAP_EID_PROP = "_snap_eid"

EXIT_SNAPSHOT_MISSING = 1
EXIT_LIVE_WRITER = 2

CYPHER_EXPORT_NODES = (
    "MATCH (n) RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props"
)
CYPHER_EXPORT_RELS = (
    "MATCH (a)-[r]->(b)"
    " RETURN elementId(a) AS src_eid, elementId(b) AS dst_eid,"
    " type(r) AS rel_type, properties(r) AS props"
)
CYPHER_WIPE = "MATCH (n) DETACH DELETE n"
CYPHER_REMOVE_SNAP_PROP = (
    f"MATCH (n) WHERE n.`{_SNAP_EID_PROP}` IS NOT NULL REMOVE n.`{_SNAP_EID_PROP}`"
)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _serialize_props(props: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe copy of a Neo4j property map.

    Neo4j temporal types (DateTime, Date, etc.) are encoded as
    ``{"__neo4j_type__": "<class>", "value": "<iso>"}`` dicts so
    that restore can write them back as plain strings without data loss.
    """
    return {k: _serialize_value(v) for k, v in props.items()}


def _serialize_value(val: Any) -> Any:
    """Recursively convert a Neo4j driver value to a JSON-serialisable form."""
    if isinstance(val, (str, int, float, bool, type(None))):
        return val
    if isinstance(val, list):
        return [_serialize_value(v) for v in val]
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    if hasattr(val, "iso_format"):
        return {"__neo4j_type__": type(val).__name__, "value": val.iso_format()}
    return str(val)


def _deserialize_props(props: dict[str, Any]) -> dict[str, Any]:
    """Return a restored property map suitable for passing back to Neo4j."""
    return {k: _deserialize_value(v) for k, v in props.items()}


def _deserialize_value(val: Any) -> Any:
    """Convert type-tagged temporal dicts back to their ISO string values."""
    if isinstance(val, dict) and "__neo4j_type__" in val:
        return val["value"]
    if isinstance(val, list):
        return [_deserialize_value(v) for v in val]
    if isinstance(val, dict):
        return {k: _deserialize_value(v) for k, v in val.items()}
    return val


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def _open_driver() -> Driver:
    """Open a sync Neo4j driver from environment or defaults."""
    uri = os.environ.get("NEO4J_URI", NEO4J_URI_DEFAULT)
    user = os.environ.get("NEO4J_USER", NEO4J_USER_DEFAULT)
    password = os.environ.get("NEO4J_PASSWORD", NEO4J_PASSWORD_DEFAULT)
    return GraphDatabase.driver(uri, auth=(user, password))


def do_snapshot(path: Path, *, strip_derived: bool = False) -> None:
    """Export all nodes and relationships to *path* as JSON.

    The format is:
    ``{"nodes": [{eid, labels, props}, ...], "rels": [{src_eid, dst_eid, rel_type, props}, ...]}``

    Args:
        path: Destination JSON file.
        strip_derived: Remove DERIVED_NODE_FIELDS before writing. Required for any
            checked-in world fixture (DEC-206 step 5, DEC-211 Decision 3).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    driver = _open_driver()
    try:
        with driver.session() as session:
            nodes = [
                {
                    "eid": record["eid"],
                    "labels": list(record["labels"]),
                    "props": _serialize_props(dict(record["props"])),
                }
                for record in session.run(CYPHER_EXPORT_NODES)
            ]
            rels = [
                {
                    "src_eid": record["src_eid"],
                    "dst_eid": record["dst_eid"],
                    "rel_type": record["rel_type"],
                    "props": _serialize_props(dict(record["props"])),
                }
                for record in session.run(CYPHER_EXPORT_RELS)
            ]
    finally:
        driver.close()

    payload: dict[str, Any] = {"nodes": nodes, "rels": rels}
    removed = 0
    if strip_derived:
        payload, removed = strip_derived_fields(payload)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"[snapshot] saved {len(nodes)} nodes, {len(rels)} relationships "
        f"(stripped {removed} derived properties) -> {path}",
        file=sys.stderr,
    )


def do_restore(path: Path) -> None:
    """Wipe the graph and restore it from *path*, atomically.

    Steps:
    1. Probe for a live writer and abort (touching nothing) if one is found.
    2. In ONE transaction: wipe, recreate each node tagged with a temporary
       ``_snap_eid`` mirroring its original element-id, recreate each relationship
       by matching on that sentinel, then strip the sentinel.

    Everything after the probe runs inside a single ``execute_write``, so any
    failure rolls the graph back to its pre-restore state instead of leaving it
    half-populated (ISSUE-188). ``CREATE`` after ``DETACH DELETE`` cannot
    self-collide: uncommitted deletes are invisible to the constraint check. The
    driver may retry the work function on transient errors, which is safe because
    the wipe is its first statement. With a writer still live the restore now
    blocks on locks and raises rather than writing a partial world.

    Args:
        path: Snapshot JSON file written by do_snapshot.
    Raises:
        SystemExit: EXIT_SNAPSHOT_MISSING if *path* does not exist,
            EXIT_LIVE_WRITER if another process is writing to the graph.
    """
    if not path.exists():
        print(f"[restore] snapshot file not found: {path}", file=sys.stderr)
        sys.exit(EXIT_SNAPSHOT_MISSING)

    payload = json.loads(path.read_text(encoding="utf-8"))
    nodes: list[dict[str, Any]] = payload["nodes"]
    rels: list[dict[str, Any]] = payload["rels"]

    driver = _open_driver()
    try:
        with driver.session() as session:
            _abort_if_writer_is_live(session)
            session.execute_write(_restore_all, nodes, rels)
    finally:
        driver.close()

    print(
        f"[restore] restored {len(nodes)} nodes, {len(rels)} relationships from {path}",
        file=sys.stderr,
    )


def _abort_if_writer_is_live(session: Any) -> None:
    """Exit with EXIT_LIVE_WRITER, having changed nothing, if the graph is moving."""
    window = probe_seconds()
    if window > 0:
        print(f"[restore] probing for live writers ({window}s) ...", file=sys.stderr)
    try:
        assert_no_live_writer(session, probe_seconds=window)
    except LiveWriterDetectedError as exc:
        print(
            f"[restore] ABORT: the graph changed during the {window}s probe"
            " -- a writer is live.",
            file=sys.stderr,
        )
        for change in exc.changes:
            print(f"  {change}", file=sys.stderr)
        print(REMEDY_HINT, file=sys.stderr)
        print("Nothing was modified.", file=sys.stderr)
        raise SystemExit(EXIT_LIVE_WRITER) from exc


def _restore_all(tx: Any, nodes: list[dict[str, Any]], rels: list[dict[str, Any]]) -> None:
    """Wipe and rebuild the whole graph inside one managed transaction."""
    tx.run(CYPHER_WIPE)
    _restore_nodes(tx, nodes)
    _restore_rels(tx, rels)
    tx.run(CYPHER_REMOVE_SNAP_PROP)


def _restore_nodes(tx: Any, nodes: list[dict[str, Any]]) -> None:
    """Create all nodes from the snapshot, each tagged with _snap_eid."""
    for node in nodes:
        labels_cypher = ":".join(f"`{lbl}`" for lbl in node["labels"]) or "Node"
        props = _deserialize_props(node["props"])
        props[_SNAP_EID_PROP] = node["eid"]
        cypher = f"CREATE (n:{labels_cypher}) SET n = $props"
        tx.run(cypher, props=props)


def _restore_rels(tx: Any, rels: list[dict[str, Any]]) -> None:
    """Create all relationships from the snapshot, matched by _snap_eid."""
    for rel in rels:
        rel_type = rel["rel_type"]
        props = _deserialize_props(rel["props"])
        cypher = (
            f"MATCH (a) WHERE a.`{_SNAP_EID_PROP}` = $src"
            f" MATCH (b) WHERE b.`{_SNAP_EID_PROP}` = $dst"
            f" CREATE (a)-[r:`{rel_type}`]->(b) SET r = $props"
        )
        tx.run(cypher, src=rel["src_eid"], dst=rel["dst_eid"], props=props)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Snapshot or restore the Neo4j demo world graph."
    )
    parser.add_argument(
        "--mode",
        choices=["snapshot", "restore"],
        required=True,
        help="'snapshot' to export, 'restore' to wipe and reimport.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_SNAPSHOT_PATH,
        help=f"Path to the snapshot JSON file (default: {DEFAULT_SNAPSHOT_PATH}).",
    )
    parser.add_argument(
        "--strip-derived",
        action="store_true",
        help=(
            "Remove derived embedding properties before writing "
            f"({', '.join(sorted(DERIVED_NODE_FIELDS))}). Required for any checked-in "
            "world fixture — see DEC-206 step 5 and DEC-211."
        ),
    )
    return parser


def main() -> None:
    """CLI entry point for demo-snapshot and demo-restore Makefile targets."""
    args = _build_parser().parse_args()
    if args.mode == "snapshot":
        do_snapshot(args.path, strip_derived=args.strip_derived)
    else:
        do_restore(args.path)


if __name__ == "__main__":
    main()
