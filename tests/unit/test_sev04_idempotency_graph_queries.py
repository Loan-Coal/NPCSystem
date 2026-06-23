"""
test_sev04_idempotency_graph_queries.py — SEV-04 regression: idempotency domain
Cypher + store lives in graph/, not engines/.
"""

from __future__ import annotations

import pytest


def test_idempotency_store_importable_from_graph_layer() -> None:
    """Neo4jIdempotencyStore must live in graph.idempotency_writer."""
    from npc_engine.graph.idempotency.idempotency_writer import Neo4jIdempotencyStore  # noqa: F401

    assert Neo4jIdempotencyStore is not None


def test_idempotency_queries_importable_from_graph_layer() -> None:
    """Cypher constants must live in graph.idempotency_queries."""
    from npc_engine.graph.idempotency.idempotency_queries import (  # noqa: F401
        CYPHER_CREATE_PENDING_IF_ABSENT,
        CYPHER_DELETE_EXPIRED,
        CYPHER_ENSURE_IDEMPOTENCY_CONSTRAINT,
        CYPHER_GET_RECORD,
        CYPHER_MARK_COMPLETE,
        CYPHER_UPSERT_PENDING,
    )

    assert CYPHER_GET_RECORD != ""


def test_idempotency_models_importable_from_graph_layer() -> None:
    """IdempotencyRecord must live in graph.idempotency_models."""
    from npc_engine.graph.idempotency.idempotency_models import IdempotencyRecord  # noqa: F401

    assert IdempotencyRecord is not None


def test_engines_idempotency_has_no_raw_session_run() -> None:
    """engines/idempotency/ must not contain session.run calls (Cypher moved to graph/)."""
    import ast
    import pathlib

    engine_dir = pathlib.Path("src/npc_engine/engines/idempotency")
    violations: list[str] = []
    for py_file in engine_dir.glob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "run":
                if isinstance(node.value, ast.Name) and node.value.id in {"session", "tx"}:
                    violations.append(f"{py_file.name}:{node.lineno}")
    assert violations == [], f"session.run in engines/idempotency/: {violations}"
