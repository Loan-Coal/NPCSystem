"""
Module: graph_vocabulary
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Fetch and cache the graph node-ID vocabulary used by deterministic scorers.
         Paged GET /v1/graph/nodes/{node_type} over Character / Location / Event / Faction
         into a frozen GraphVocabulary Pydantic model; cached to
         evals/generations/<gen_id>/vocabulary.json so scoring is replayable
         with the engine down.
Dependencies: any HTTP client with .get(url, *, params), pydantic v2, pathlib, typing
Used by: evals.deterministic_pass
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NODE_TYPES: tuple[str, ...] = ("Character", "Location", "Event", "Faction")
_DEFAULT_PAGE_SIZE: int = 100
_CACHE_FILENAME: str = "vocabulary.json"
_NODE_ID_FIELD: str = "id"

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
# Pydantic model
# ---------------------------------------------------------------------------


class GraphVocabulary(BaseModel):
    """Frozen snapshot of all node IDs fetched from the graph.

    Attributes:
        node_types: Node type labels that were included in this snapshot.
        ids: Frozen set of every node ID string across all fetched types.
    """

    model_config = ConfigDict(frozen=True)

    node_types: tuple[str, ...] = NODE_TYPES
    ids: frozenset[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_node_ids(
    client: HttpClient,
    base_url: str,
    node_type: str,
    *,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> list[str]:
    """Fetch all node IDs for one node type using offset pagination.

    Issues pages of ``page_size`` items until a short page (len < page_size)
    signals that no more items remain.

    Args:
        client: HTTP client satisfying HttpClient protocol.
        base_url: Engine base URL (e.g. ``"http://localhost:8000"``).
        node_type: Graph node type label (e.g. ``"Character"``).
        page_size: Maximum items per page; also the termination threshold.
    Returns:
        List of all node ID strings for this type, in fetch order.
    Raises:
        httpx.HTTPStatusError: On non-2xx responses.
    """
    ids: list[str] = []
    offset = 0
    while True:
        resp = client.get(
            f"{base_url}/v1/graph/nodes/{node_type}",
            params={"limit": page_size, "offset": offset},
        )
        resp.raise_for_status()
        page: list[dict[str, Any]] = resp.json()["data"]
        for node in page:
            node_id = node.get(_NODE_ID_FIELD)
            if node_id is not None:
                ids.append(str(node_id))
        if len(page) < page_size:
            break
        offset += page_size
    return ids


def _load_from_cache(cache_path: Path) -> GraphVocabulary:
    """Deserialise a GraphVocabulary from a JSON cache file.

    Args:
        cache_path: Path to a vocabulary.json written by a prior fetch.
    Returns:
        Validated, frozen GraphVocabulary.
    """
    return GraphVocabulary.model_validate_json(cache_path.read_text(encoding="utf-8"))


def _save_to_cache(vocab: GraphVocabulary, gen_dir: Path) -> None:
    """Persist a GraphVocabulary to gen_dir/vocabulary.json.

    Creates gen_dir (and parents) if it does not exist.

    Args:
        vocab: Vocabulary snapshot to serialise.
        gen_dir: Generation directory that receives the cache file.
    """
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / _CACHE_FILENAME).write_text(vocab.model_dump_json(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_vocabulary(
    client: HttpClient,
    base_url: str,
    gen_dir: Path | None = None,
    *,
    node_types: tuple[str, ...] = NODE_TYPES,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> GraphVocabulary:
    """Return the graph vocabulary, serving from cache when available.

    If *gen_dir* is provided and ``vocabulary.json`` already exists there,
    returns the cached GraphVocabulary with **zero** HTTP requests.  Otherwise
    fetches all pages for every type in *node_types*, writes the result to
    cache (when *gen_dir* is given), and returns it.

    Args:
        client: HTTP client satisfying HttpClient protocol.
        base_url: Engine base URL.
        gen_dir: Generation directory for cache I/O; ``None`` disables caching.
        node_types: Node type labels to include in the vocabulary.
        page_size: Pagination page size for HTTP fetch.
    Returns:
        Frozen GraphVocabulary containing every node ID for the requested types.
    """
    if gen_dir is not None:
        cache_path = gen_dir / _CACHE_FILENAME
        if cache_path.exists():
            return _load_from_cache(cache_path)

    all_ids: set[str] = set()
    for node_type in node_types:
        all_ids.update(_fetch_node_ids(client, base_url, node_type, page_size=page_size))

    vocab = GraphVocabulary(node_types=node_types, ids=frozenset(all_ids))

    if gen_dir is not None:
        _save_to_cache(vocab, gen_dir)

    return vocab
