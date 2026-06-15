"""
pagination.py - Isolated pagination strategy helpers for API routes.
Layer: api
Purpose: (auto-detected — review)

Does NOT: query storage layers directly.

Dependencies injected: None.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


DEFAULT_LIMIT = 50
MAX_LIMIT = 200
DEFAULT_OFFSET = 0
DEFAULT_SORT = "id:asc"


class PaginationStrategy(StrEnum):
    """Supported pagination strategy identifiers."""

    OFFSET = "offset"


@dataclass(frozen=True)
class OffsetPagination:
    """Resolved offset pagination values used by route and service layers."""

    limit: int
    offset: int
    sort: str
    strategy: PaginationStrategy = PaginationStrategy.OFFSET


def resolve_offset_pagination(*, limit: int | None, offset: int | None) -> OffsetPagination:
    """Resolve bounded offset pagination values with deterministic defaults."""

    resolved_limit = DEFAULT_LIMIT if limit is None else max(1, min(MAX_LIMIT, limit))
    resolved_offset = DEFAULT_OFFSET if offset is None else max(0, offset)
    return OffsetPagination(limit=resolved_limit, offset=resolved_offset, sort=DEFAULT_SORT)
