"""
embedding_reconciler.py - Background stale-embedding reconciliation worker.

Does NOT: mutate core graph properties other than embedding index timestamps.

Dependencies injected: GraphDB and EmbeddingIndex.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Protocol


LOGGER = logging.getLogger(__name__)


CYPHER_SELECT_STALE_NODES = """
MATCH (n:Character)
WHERE n.is_active = true
  AND n.id IS NOT NULL
  AND n.last_graph_updated_at IS NOT NULL
  AND (
      n.last_embedding_indexed_at IS NULL
      OR n.last_graph_updated_at > n.last_embedding_indexed_at
  )
RETURN n.id AS id,
       'Character' AS kind,
       trim(coalesce(n.name, '') + ' ' + coalesce(n.archetype, '') + ' ' + coalesce(n.biography, '') + ' ' + coalesce(n.current_mood, '')) AS text,
       properties(n) AS payload
UNION ALL
MATCH (n:Event)
WHERE n.id IS NOT NULL
  AND n.last_graph_updated_at IS NOT NULL
  AND (
      n.last_embedding_indexed_at IS NULL
      OR n.last_graph_updated_at > n.last_embedding_indexed_at
  )
RETURN n.id AS id,
       'Event' AS kind,
       trim(coalesce(n.summary, '') + ' ' + coalesce(n.event_type, '') + ' ' + coalesce(n.location_id, '')) AS text,
       properties(n) AS payload
UNION ALL
MATCH (n:Location)
WHERE n.id IS NOT NULL
  AND n.last_graph_updated_at IS NOT NULL
  AND (
      n.last_embedding_indexed_at IS NULL
      OR n.last_graph_updated_at > n.last_embedding_indexed_at
  )
RETURN n.id AS id,
       'Location' AS kind,
       trim(coalesce(n.name, '') + ' ' + coalesce(n.descriptor, '') + ' ' + coalesce(n.region, '') + ' ' + coalesce(n.location_tag, '')) AS text,
       properties(n) AS payload
"""


_MARK_INDEXED_QUERIES: dict[str, str] = {
    "Character": "MATCH (n:Character {id: $node_id}) SET n.last_embedding_indexed_at = datetime($indexed_at)",
    "Event": "MATCH (n:Event {id: $node_id}) SET n.last_embedding_indexed_at = datetime($indexed_at)",
    "Location": "MATCH (n:Location {id: $node_id}) SET n.last_embedding_indexed_at = datetime($indexed_at)",
}


class _SessionProtocol(Protocol):
    async def run(self, query: str, **params):
        """Execute an async Cypher query."""


class _GraphDbProtocol(Protocol):
    def get_session(self):
        """Return async context manager yielding sessions."""


class _EmbeddingIndexProtocol(Protocol):
    async def upsert(self, item_id: str, text: str, payload: dict) -> None:
        """Upsert one embedding row."""


class EmbeddingReconciler:
    """Periodic reconciler that heals stale embeddings from graph timestamps."""

    def __init__(
        self,
        graph_db: _GraphDbProtocol,
        embedding_index: _EmbeddingIndexProtocol,
        interval_seconds: int,
        batch_size: int = 200,
    ):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than 0")
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")
        self._graph_db = graph_db
        self._embedding_index = embedding_index
        self._interval_seconds = interval_seconds
        self._batch_size = batch_size

    async def reconcile_once(self) -> dict[str, int]:
        """Run one reconciliation cycle and return processed/failed counters."""

        async with self._graph_db.get_session() as session:
            return await self._reconcile_in_session(session=session)

    async def run_forever(self) -> None:
        """Run reconciliation cycles until task cancellation."""

        while True:
            try:
                stats = await self.reconcile_once()
                if stats["processed"] > 0 or stats["failed"] > 0:
                    LOGGER.info(
                        "embedding reconcile cycle finished: processed=%s failed=%s",
                        stats["processed"],
                        stats["failed"],
                    )
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                LOGGER.info("embedding reconciler cancelled")
                raise
            except Exception:
                LOGGER.exception("embedding reconciler cycle failed")
                await asyncio.sleep(self._interval_seconds)

    async def _reconcile_in_session(self, session: _SessionProtocol) -> dict[str, int]:
        result = await session.run(CYPHER_SELECT_STALE_NODES)

        processed = 0
        failed = 0
        seen = 0
        async for record in result:
            if seen >= self._batch_size:
                break
            seen += 1
            node_id = str(_record_value(record=record, key="id", default=""))
            kind = str(_record_value(record=record, key="kind", default=""))
            text = str(_record_value(record=record, key="text", default="")).strip()
            if text == "":
                text = node_id

            payload_raw = _record_value(record=record, key="payload", default={})
            payload = payload_raw if isinstance(payload_raw, dict) else {}
            indexed_at = datetime.now(timezone.utc).isoformat()
            payload_with_meta = {
                **payload,
                "id": node_id,
                "kind": kind,
                "indexed_at": indexed_at,
            }

            try:
                await self._embedding_index.upsert(item_id=node_id, text=text, payload=payload_with_meta)
                await self._mark_node_indexed(
                    session=session,
                    kind=kind,
                    node_id=node_id,
                    indexed_at=indexed_at,
                )
                processed += 1
            except Exception:
                failed += 1
                LOGGER.exception("embedding reconcile failed for kind=%s id=%s", kind, node_id)

        return {"processed": processed, "failed": failed}

    async def _mark_node_indexed(self, session: _SessionProtocol, kind: str, node_id: str, indexed_at: str) -> None:
        query = _MARK_INDEXED_QUERIES.get(kind)
        if query is None:
            return
        await session.run(query, node_id=node_id, indexed_at=indexed_at)


def _record_value(record: Any, key: str, default: Any) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    try:
        return record[key]
    except Exception:
        return default
