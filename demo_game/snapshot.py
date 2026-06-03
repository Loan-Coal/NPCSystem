"""
Module: snapshot
Layer: demo_game (standalone CLI tool — no engine layer imports)
Purpose: Export and restore Neo4j graph state for demo resets between takes.
Dependencies: neo4j (sync driver), json, pathlib, argparse, os
Used by: Makefile targets demo-snapshot and demo-restore
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase, Driver

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SNAPSHOT_PATH = Path(".cache/demo/snapshot.json")

NEO4J_URI_DEFAULT = "bolt://localhost:7687"
NEO4J_USER_DEFAULT = "neo4j"
NEO4J_PASSWORD_DEFAULT = "password"

_SNAP_EID_PROP = "_snap_eid"

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


def do_snapshot(path: Path) -> None:
    """Export all nodes and relationships to *path* as JSON.

    The format is:
    ``{"nodes": [{eid, labels, props}, ...], "rels": [{src_eid, dst_eid, rel_type, props}, ...]}``
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

    payload = {"nodes": nodes, "rels": rels}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"[snapshot] saved {len(nodes)} nodes, {len(rels)} relationships → {path}",
        file=sys.stderr,
    )


def do_restore(path: Path) -> None:
    """Wipe the graph and restore it from *path*.

    Steps:
    1. Wipe all nodes and relationships.
    2. Recreate each node, tagging it with a temporary ``_snap_eid`` property
       that mirrors the original Neo4j element-id so relationships can be matched.
    3. Recreate each relationship by matching on ``_snap_eid``.
    4. Strip the ``_snap_eid`` sentinel from every node.
    """
    if not path.exists():
        print(f"[restore] snapshot file not found: {path}", file=sys.stderr)
        sys.exit(1)

    payload = json.loads(path.read_text(encoding="utf-8"))
    nodes: list[dict[str, Any]] = payload["nodes"]
    rels: list[dict[str, Any]] = payload["rels"]

    driver = _open_driver()
    try:
        with driver.session() as session:
            session.run(CYPHER_WIPE)
            _restore_nodes(session, nodes)
            _restore_rels(session, rels)
            session.run(CYPHER_REMOVE_SNAP_PROP)
    finally:
        driver.close()

    print(
        f"[restore] restored {len(nodes)} nodes, {len(rels)} relationships from {path}",
        file=sys.stderr,
    )


def _restore_nodes(session: Any, nodes: list[dict[str, Any]]) -> None:
    """Create all nodes from the snapshot, each tagged with _snap_eid."""
    for node in nodes:
        labels_cypher = ":".join(f"`{lbl}`" for lbl in node["labels"]) or "Node"
        props = _deserialize_props(node["props"])
        props[_SNAP_EID_PROP] = node["eid"]
        cypher = f"CREATE (n:{labels_cypher}) SET n = $props"
        session.run(cypher, props=props)


def _restore_rels(session: Any, rels: list[dict[str, Any]]) -> None:
    """Create all relationships from the snapshot, matched by _snap_eid."""
    for rel in rels:
        rel_type = rel["rel_type"]
        props = _deserialize_props(rel["props"])
        cypher = (
            f"MATCH (a) WHERE a.`{_SNAP_EID_PROP}` = $src"
            f" MATCH (b) WHERE b.`{_SNAP_EID_PROP}` = $dst"
            f" CREATE (a)-[r:`{rel_type}`]->(b) SET r = $props"
        )
        session.run(cypher, src=rel["src_eid"], dst=rel["dst_eid"], props=props)


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
    return parser


def main() -> None:
    """CLI entry point for demo-snapshot and demo-restore Makefile targets."""
    args = _build_parser().parse_args()
    if args.mode == "snapshot":
        do_snapshot(args.path)
    else:
        do_restore(args.path)


if __name__ == "__main__":
    main()
