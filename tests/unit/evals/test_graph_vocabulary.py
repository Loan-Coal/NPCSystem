"""
Module: test_graph_vocabulary
Layer: test (unit)
Purpose: Tests for evals/graph_vocabulary.py — paged fetch, GraphVocabulary model,
         and cache hit/miss behaviour. All tests use a mock HTTP client; no live
         engine or Neo4j required.
Dependencies: pytest, pathlib; graph_vocabulary (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from graph_vocabulary import GraphVocabulary, fetch_vocabulary

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_PAGE_SIZE = 2


class _MockResponse:
    """Minimal httpx-like response stub."""

    def __init__(self, items: list[str]) -> None:
        self._data = [{"id": item_id} for item_id in items]

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return {"data": self._data, "success": True}


class _MockClient:
    """HTTP mock that serves pre-configured pages indexed by offset."""

    def __init__(self, pages: list[list[str]]) -> None:
        self._pages = pages
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, params: dict[str, Any] | None = None) -> _MockResponse:
        self.calls.append({"url": url, "params": dict(params or {})})
        p = params or {}
        offset = int(p.get("offset", 0))
        limit = int(p.get("limit", _PAGE_SIZE))
        page_idx = offset // limit if limit > 0 else 0
        page = self._pages[page_idx] if page_idx < len(self._pages) else []
        return _MockResponse(page)


# ---------------------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------------------


def test_paginates_until_short_page() -> None:
    """Issues exactly 3 requests (two full, one short) and holds every id."""
    pages = [
        ["id_a1", "id_a2"],  # full (len == page_size)
        ["id_b1", "id_b2"],  # full
        ["id_c1"],            # short → terminates loop
    ]
    client = _MockClient(pages)

    vocab = fetch_vocabulary(
        client,
        "http://fake",
        node_types=("Character",),
        page_size=_PAGE_SIZE,
    )

    assert len(client.calls) == 3
    assert {"id_a1", "id_a2", "id_b1", "id_b2", "id_c1"} <= vocab.ids


def test_single_short_page_issues_one_request() -> None:
    """When the first page is already short, only one request is made."""
    client = _MockClient([["id_x"]])
    vocab = fetch_vocabulary(
        client, "http://fake", node_types=("Event",), page_size=_PAGE_SIZE
    )
    assert len(client.calls) == 1
    assert "id_x" in vocab.ids


def test_empty_node_type_issues_one_request() -> None:
    """An empty node type issues exactly one request and contributes no IDs."""
    client = _MockClient([[]])
    vocab = fetch_vocabulary(
        client, "http://fake", node_types=("Faction",), page_size=_PAGE_SIZE
    )
    assert len(client.calls) == 1
    assert len(vocab.ids) == 0


def test_multiple_node_types_each_issue_at_least_one_request() -> None:
    """Each requested node type produces at least one HTTP request."""
    client = _MockClient([["char_1"]])
    fetch_vocabulary(
        client, "http://fake", node_types=("Character", "Location"), page_size=_PAGE_SIZE
    )
    assert len(client.calls) == 2


def test_ids_from_all_pages_present_in_vocabulary() -> None:
    """Vocabulary holds every ID from all pages including the terminal short page."""
    pages = [["a", "b"], ["c"]]
    client = _MockClient(pages)
    vocab = fetch_vocabulary(
        client, "http://fake", node_types=("Location",), page_size=_PAGE_SIZE
    )
    assert vocab.ids == frozenset({"a", "b", "c"})


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------


def test_cache_hit_issues_zero_requests(tmp_path: Path) -> None:
    """With vocabulary.json present in gen_dir, no HTTP requests are made."""
    cached = GraphVocabulary(ids=frozenset({"cached_id_1", "cached_id_2"}))
    (tmp_path / "vocabulary.json").write_text(
        cached.model_dump_json(), encoding="utf-8"
    )

    client = _MockClient([["live_id"]])
    result = fetch_vocabulary(client, "http://fake", gen_dir=tmp_path)

    assert len(client.calls) == 0
    assert "cached_id_1" in result.ids
    assert "cached_id_2" in result.ids
    assert "live_id" not in result.ids


def test_fetch_writes_vocabulary_to_cache(tmp_path: Path) -> None:
    """After a live fetch, vocabulary.json is written to gen_dir."""
    client = _MockClient([["new_id"]])
    fetch_vocabulary(
        client,
        "http://fake",
        gen_dir=tmp_path,
        node_types=("Character",),
        page_size=_PAGE_SIZE,
    )
    assert (tmp_path / "vocabulary.json").exists()


def test_no_gen_dir_skips_cache_write(tmp_path: Path) -> None:
    """Without gen_dir, no vocabulary.json file is written."""
    client = _MockClient([["id_q"]])
    fetch_vocabulary(
        client, "http://fake", node_types=("Character",), page_size=_PAGE_SIZE
    )
    assert not any(tmp_path.iterdir())


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_graph_vocabulary_is_frozen() -> None:
    """GraphVocabulary is immutable — attribute mutation raises an error."""
    vocab = GraphVocabulary(ids=frozenset({"id_1"}))
    with pytest.raises(ValidationError, match="Instance is frozen"):
        vocab.ids = frozenset()  # type: ignore[misc]
