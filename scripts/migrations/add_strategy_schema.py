"""
Migration: add_strategy_schema

Adds uniqueness constraints for ResourceNode and Army nodes (Phase 7.4 Strategy/4X).
No backfill needed — these nodes are created fresh during gameplay.

Usage:
    python scripts/migrations/add_strategy_schema.py [--dry-run]

Exit codes:
    0 — success (or dry-run preview completed)
    1 — failure
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from neo4j import AsyncGraphDatabase

_LOGGER = logging.getLogger(__name__)

_CONSTRAINTS: list[str] = [
    (
        "CREATE CONSTRAINT resource_node_id_unique IF NOT EXISTS "
        "FOR (r:ResourceNode) REQUIRE r.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT army_id_unique IF NOT EXISTS "
        "FOR (a:Army) REQUIRE a.id IS UNIQUE"
    ),
]


async def _apply(uri: str, user: str, password: str, *, dry_run: bool) -> None:
    """Apply (or preview) all schema constraints."""
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            for statement in _CONSTRAINTS:
                if dry_run:
                    _LOGGER.info("[DRY-RUN] %s", statement)
                else:
                    await session.run(statement)
                    _LOGGER.info("Applied: %s", statement)
    finally:
        await driver.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Phase 7.4 strategy schema migration.")
    parser.add_argument("--dry-run", action="store_true", help="Print statements without executing.")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", default="password")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args()
    try:
        asyncio.run(_apply(args.uri, args.user, args.password, dry_run=args.dry_run))
    except Exception:
        _LOGGER.exception("Migration failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
