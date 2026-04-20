"""
test_pagination_strategy.py - Unit tests for isolated offset pagination strategy.

Does NOT: exercise API routes or database access.

Dependencies injected: None.
"""

from api.pagination import PaginationStrategy, resolve_offset_pagination


def test_resolve_offset_pagination_uses_defaults() -> None:
    """Pagination helper should use configured defaults when explicit values are absent."""

    page = resolve_offset_pagination(limit=None, offset=None)

    assert page.limit == 50
    assert page.offset == 0
    assert page.strategy == PaginationStrategy.OFFSET
    assert page.sort == "id:asc"


def test_resolve_offset_pagination_clamps_limit_to_max() -> None:
    """Pagination helper should clamp requested limit to configured maximum."""

    page = resolve_offset_pagination(limit=999, offset=10)

    assert page.limit == 200
    assert page.offset == 10


def test_resolve_offset_pagination_rejects_negative_offset() -> None:
    """Pagination helper should normalize offset to zero for invalid negative values."""

    page = resolve_offset_pagination(limit=10, offset=-20)

    assert page.limit == 10
    assert page.offset == 0
