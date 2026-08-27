"""
Module: derived_fields
Layer: demo_game (standalone CLI support — no engine layer imports)
Purpose: Name the node properties that are DERIVED from world state, and strip them out
         of a snapshot before it is committed as a fixture.
Dependencies: none (pure data + one pure function).
Used by: demo_game.snapshot (re-exports both names and wires --strip-derived).

Split out of snapshot.py, which is at its 300-line cap; this is a coherent unit on its
own and is the artifact DEC-211 Decision 3 asks for.
"""

from __future__ import annotations

from typing import Any

__all__ = ["DERIVED_NODE_FIELDS", "strip_derived_fields"]

DERIVED_NODE_FIELDS: frozenset[str] = frozenset({
    "embedding",
    "last_embedding_indexed_at",
    "embedding_model",
    "embedding_dim",
})
"""Node properties that are DERIVED from world state and must not enter a fixture.

DEC-206 rules that embeddings are derived data: they tripled the eval baseline
(154 KB -> 576 KB) and coupled a world fixture to whatever EMBEDDING_MODEL produced
them. DEC-211 Decision 1 added `embedding_model` and `embedding_dim`, growing this list
from two entries to four — which is exactly why it had to stop being a script in a
session-scoped temp directory and become something a clean checkout can run.

DEC-206's procedure step 4/5 is now:

    python -m demo_game.snapshot --mode snapshot --path <out.json> --strip-derived

or `make eval-world-snapshot`.
"""


def strip_derived_fields(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Return a copy of *payload* with every DERIVED_NODE_FIELDS property removed.

    Pure: the input is never mutated. A regeneration that half-strips its own source in
    memory and then fails is unrecoverable, and this runs immediately before a fixture
    is written.

    Args:
        payload: Snapshot dict with "nodes" and "rels" keys.

    Returns:
        Tuple of (stripped payload, number of properties removed). The count is printed
        by the CLI: a `stripped 0` on a freshly-ticked world means the strip did not run.
    """
    removed = 0
    nodes = []
    for node in payload.get("nodes", []):
        props = {k: v for k, v in node.get("props", {}).items() if k not in DERIVED_NODE_FIELDS}
        removed += len(node.get("props", {})) - len(props)
        nodes.append({**node, "props": props})
    return {**payload, "nodes": nodes}, removed
