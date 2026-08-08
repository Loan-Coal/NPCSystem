"""
Module: case_drafts
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Draft YAML capability-case generator over the graph API.
         For each (NPC, grounded-fact) pair reachable via
         GET /v1/graph/edges/{edge_type}?src_id={npc_id}, emits a draft YAML
         case file into evals/cases/_drafts/. Drafts are never loaded by the
         runner; they require human review before promotion to evals/cases/.
Dependencies: pydantic v2, yaml, pathlib, re, typing
Used by: evals/__main__.py (draft-cases verb),
         tests/unit/evals/test_case_drafts.py
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROUNDED_EDGE_TYPES: tuple[str, ...] = (
    "KNOWS_ABOUT",
    "BELIEVES",
    "HAS_MEMORY",
    "HAS_GOAL",
    "HAS_SECRET",
)

_DEFAULT_BASE_URL: str = "http://localhost:8000"
_DRAFTS_SUBDIR: str = "_drafts"
_DEFAULT_PLAYER_ID: str = "player_eval"
_PAGE_SIZE: int = 100
_DEFAULT_REQUIRES_WORLD: str = "demo"

# Simple eliciting message templates; {fact_id} is replaced with a
# human-readable version of the fact node ID (underscores → spaces).
_MESSAGE_TEMPLATES: dict[str, str] = {
    "KNOWS_ABOUT": "What do you know about {fact_id}?",
    "BELIEVES": "What do you believe about {fact_id}?",
    "HAS_MEMORY": "Can you tell me about your experience with {fact_id}?",
    "HAS_GOAL": "What are your plans regarding {fact_id}?",
    "HAS_SECRET": "Is there something you're not telling me about {fact_id}?",
}

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class HttpClient(Protocol):
    """Minimal HTTP client interface — satisfied by httpx.Client.

    Any object with a .get(url, *, params) method returning an object with
    .raise_for_status() and .json() qualifies.
    """

    def get(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        """Issue a GET request and return an HTTP response object."""
        ...


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class GroundedEdge(BaseModel):
    """One knowledge edge connecting an NPC to a fact node.

    Attributes:
        src_id: NPC node ID (edge source).
        dst_id: Fact node ID (edge destination).
        edge_type: Relationship type label (e.g. KNOWS_ABOUT).
        properties: Raw additional edge properties from the graph.
    """

    model_config = ConfigDict(frozen=True)

    src_id: str
    dst_id: str
    edge_type: str
    properties: dict[str, Any] = {}


class DraftResult(BaseModel):
    """Summary of a draft generation run.

    Attributes:
        written: Draft file paths that were written (new or overwritten).
        skipped: Draft file paths that already existed and were not rewritten.
    """

    model_config = ConfigDict(frozen=True)

    written: tuple[Path, ...] = ()
    skipped: tuple[Path, ...] = ()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_grounded_edges(
    client: HttpClient,
    base_url: str,
    npc_id: str,
    edge_types: tuple[str, ...] = GROUNDED_EDGE_TYPES,
) -> list[GroundedEdge]:
    """Fetch all grounded knowledge edges for one NPC via offset pagination.

    Args:
        client: HTTP client satisfying HttpClient protocol.
        base_url: Engine base URL (e.g. "http://localhost:8000").
        npc_id: NPC node ID to use as the edge source filter.
        edge_types: Relationship types to query.
    Returns:
        List of GroundedEdge instances for this NPC across all edge types.
    Raises:
        httpx.HTTPStatusError: On non-2xx responses.
    """
    edges: list[GroundedEdge] = []
    for edge_type in edge_types:
        offset = 0
        while True:
            resp = client.get(
                f"{base_url}/v1/graph/edges/{edge_type}",
                params={"src_id": npc_id, "limit": _PAGE_SIZE, "offset": offset},
            )
            resp.raise_for_status()
            page: list[dict[str, Any]] = resp.json()["data"]
            for item in page:
                edges.append(
                    GroundedEdge(
                        src_id=npc_id,
                        dst_id=item["dst_id"],
                        edge_type=edge_type,
                        properties={
                            k: v for k, v in item.items() if k not in ("src_id", "dst_id")
                        },
                    )
                )
            if len(page) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
    return edges


def _fact_tokens(fact_id: str) -> list[str]:
    """Extract lower-case keyword tokens from a fact node ID.

    Args:
        fact_id: Fact node ID (e.g. "northern_war_begins").
    Returns:
        List of lower-case tokens (e.g. ["northern", "war", "begins"]).
    """
    return [t.lower() for t in re.split(r"[_\-]", fact_id) if t]


def _draft_filename(npc_id: str, edge_type: str, fact_id: str) -> str:
    """Compute a deterministic draft filename from the edge triple.

    The filename is stable across runs, making generation idempotent.

    Args:
        npc_id: NPC node ID.
        edge_type: Edge type label.
        fact_id: Fact node ID.
    Returns:
        Filename string (no directory prefix).
    """
    safe_edge = edge_type.lower()
    raw = f"{npc_id}_{safe_edge}_{fact_id}"
    slug = re.sub(r"[^a-z0-9_]", "_", raw)
    return f"draft_{slug}.yaml"


def _player_message(edge_type: str, fact_id: str) -> str:
    """Build a template eliciting player message for the draft.

    Args:
        edge_type: Edge type label.
        fact_id: Fact node ID (underscores are replaced with spaces).
    Returns:
        Plain-English player message string.
    """
    template = _MESSAGE_TEMPLATES.get(edge_type, "Tell me about {fact_id}.")
    return template.format(fact_id=fact_id.replace("_", " "))


def _build_draft_yaml(edge: GroundedEdge, requires_world: str) -> str:
    """Render a draft YAML case string for one grounded edge.

    The output is a ``# grounded_by:`` comment header followed by a YAML
    document matching the capability-case contract (docs/CAPABILITY_CASES.md).

    Args:
        edge: Grounded edge to produce a draft for.
        requires_world: World tag written into the draft's seed block.
    Returns:
        YAML text string with leading ``# grounded_by:`` comment.
    """
    tokens = _fact_tokens(edge.dst_id)
    raw_slug = f"{edge.src_id}_{edge.dst_id}"
    slug = re.sub(r"[^a-z0-9_]", "_", raw_slug)
    case_id = f"case_pos_{slug}"
    player_msg = _player_message(edge.edge_type, edge.dst_id)
    grounded_comment = f"# grounded_by: {edge.edge_type}({edge.src_id}, {edge.dst_id})"

    body: dict[str, Any] = {
        "case_id": case_id,
        "description": (
            f"{edge.src_id} holds a {edge.edge_type} edge to {edge.dst_id}. "
            f"Asked a fair question, they should surface relevant tokens."
        ),
        "seed": {
            "npc_id": edge.src_id,
            "player_id": _DEFAULT_PLAYER_ID,
            "requires_world": requires_world,
        },
        "input": {"player_message": player_msg},
        "expected": [
            {"kind": "schema"},
            {"kind": "keyword_any", "keywords": tokens},
        ],
        "notes": (
            f"DRAFT — review before promoting. "
            f"Grounding: {edge.edge_type}({edge.src_id}, {edge.dst_id})."
        ),
    }
    return grounded_comment + "\n" + yaml.dump(body, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_drafts(
    client: HttpClient,
    npc_ids: list[str],
    drafts_dir: Path,
    *,
    base_url: str = _DEFAULT_BASE_URL,
    requires_world: str = _DEFAULT_REQUIRES_WORLD,
    edge_types: tuple[str, ...] = GROUNDED_EDGE_TYPES,
    overwrite: bool = False,
) -> DraftResult:
    """Generate draft capability-case YAML files for all grounded NPC edges.

    For each (NPC, grounded-fact) pair fetched from the graph, writes one YAML
    file to *drafts_dir*. Existing files are skipped unless *overwrite* is
    True, making the call idempotent by default.

    Args:
        client: HTTP client satisfying HttpClient protocol.
        npc_ids: List of NPC node IDs to enumerate.
        drafts_dir: Directory where draft YAML files are written (created if absent).
        base_url: Engine base URL.
        requires_world: World tag written into each draft's seed block.
        edge_types: Edge types to enumerate per NPC.
        overwrite: When False (default), skip already-existing draft files.
    Returns:
        DraftResult summarising written and skipped paths.
    """
    drafts_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    skipped: list[Path] = []

    for npc_id in npc_ids:
        edges = _fetch_grounded_edges(client, base_url, npc_id, edge_types)
        for edge in edges:
            filename = _draft_filename(edge.src_id, edge.edge_type, edge.dst_id)
            dest = drafts_dir / filename
            if dest.exists() and not overwrite:
                skipped.append(dest)
                continue
            dest.write_text(_build_draft_yaml(edge, requires_world), encoding="utf-8")
            written.append(dest)

    return DraftResult(written=tuple(written), skipped=tuple(skipped))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ``python -m evals draft-cases``.

    Fetches all Character nodes from the graph, enumerates their grounded edges,
    and writes draft YAML capability cases to evals/cases/_drafts/.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        Exit code 0 on success, 1 on import or runtime error.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Generate draft capability cases from the live graph."
    )
    parser.add_argument(
        "--base-url",
        default=_DEFAULT_BASE_URL,
        help="Engine base URL (default: %(default)s).",
    )
    parser.add_argument(
        "--npc-ids",
        nargs="+",
        metavar="NPC_ID",
        help="NPC IDs to enumerate (default: all Character nodes).",
    )
    parser.add_argument(
        "--drafts-dir",
        default=str(Path(__file__).resolve().parent / "cases" / _DRAFTS_SUBDIR),
        help="Directory for draft YAML output (default: %(default)s).",
    )
    parser.add_argument(
        "--requires-world",
        default=_DEFAULT_REQUIRES_WORLD,
        help="World tag for seed blocks (default: %(default)s).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing draft files instead of skipping them.",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        import httpx
        from graph_vocabulary import fetch_vocabulary
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    client = httpx.Client()
    npc_ids: list[str] = args.npc_ids or []
    if not npc_ids:
        vocab = fetch_vocabulary(client, args.base_url, node_types=("Character",))
        npc_ids = sorted(vocab.ids)

    result = generate_drafts(
        client,
        npc_ids,
        Path(args.drafts_dir),
        base_url=args.base_url,
        requires_world=args.requires_world,
        overwrite=args.overwrite,
    )
    written_count = len(result.written)
    skipped_count = len(result.skipped)
    print(f"draft-cases: {written_count} written, {skipped_count} skipped → {args.drafts_dir}")
    return 0
