"""
test_snapshot_strip_derived.py - DEC-211 Decision 3.

DEC-206's procedure step 5 — "strip the derived embedding fields" — was performed by a
script in a session-scoped temp directory: not in the repo, not in the Makefile, and
surviving between sessions only by luck. DEC-211 Decision 1 grows that list from two
fields to four, so the procedure has to be executable from a clean checkout.

Does NOT: connect to Neo4j.

Dependencies injected: a temp file path.
"""

from __future__ import annotations

import json

from demo_game.snapshot import DERIVED_NODE_FIELDS, strip_derived_fields


def test_every_derived_embedding_field_is_named() -> None:
    """All four, not the two the scratchpad script knew about."""
    assert DERIVED_NODE_FIELDS == frozenset({
        "embedding", "last_embedding_indexed_at", "embedding_model", "embedding_dim",
    })


def test_stripping_removes_derived_fields_and_leaves_world_state_alone() -> None:
    payload = {
        "nodes": [
            {
                "eid": "1",
                "labels": ["Character"],
                "props": {
                    "id": "npc_1",
                    "name": "Mira",
                    "embedding": [0.1] * 384,
                    "embedding_model": "all-MiniLM-L6-v2",
                    "embedding_dim": 384,
                    "last_embedding_indexed_at": "2026-08-27T00:00:00Z",
                    "last_graph_updated_at": "2026-08-27T00:00:00Z",
                },
            }
        ],
        "rels": [{"src_eid": "1", "dst_eid": "2", "rel_type": "KNOWS_ABOUT", "props": {}}],
    }

    stripped, removed = strip_derived_fields(payload)

    props = stripped["nodes"][0]["props"]
    assert set(props) == {"id", "name", "last_graph_updated_at"}
    assert removed == 4
    assert stripped["rels"] == payload["rels"]


def test_stripping_is_a_no_op_on_a_fixture_that_carries_no_embeddings() -> None:
    """The checked-in baseline is already stripped; running it again must be safe."""
    payload = {"nodes": [{"eid": "1", "labels": ["Event"], "props": {"id": "evt_1"}}], "rels": []}

    stripped, removed = strip_derived_fields(payload)

    assert removed == 0
    assert stripped == payload


def test_stripping_does_not_mutate_its_input(tmp_path) -> None:
    """A regeneration that half-strips its own source in memory is unrecoverable."""
    payload = {
        "nodes": [{"eid": "1", "labels": ["Character"], "props": {"id": "npc_1", "embedding": [0.1]}}],
        "rels": [],
    }
    before = json.dumps(payload, sort_keys=True)

    strip_derived_fields(payload)

    assert json.dumps(payload, sort_keys=True) == before
