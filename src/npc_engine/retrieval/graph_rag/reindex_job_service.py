"""
Module: reindex_job_service
Layer: retrieval
Purpose: In-memory lifecycle manager for admin reindex jobs (relocated from graph/ in SEV-31).
Does NOT: implement graph mutation business logic.
Dependencies injected: EmbeddingIndex.
Internal dependencies: retrieval.embedding_index
Used by: api.dependency_singletons, api.routes.graph_admin
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from npc_engine.retrieval.embedding.embedding_index import EmbeddingIndex


class ReindexJobService:
    """Track and execute background reindex jobs for admin routes."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}

    def submit_reindex(self, npc_ids: list[str], embedding_index: EmbeddingIndex) -> str:
        """Queue a reindex job and return its generated identifier.

        Args:
            npc_ids: List of NPC character IDs whose embeddings need invalidation.
            embedding_index: Embedding index instance used to execute the invalidation calls.

        Returns:
            UUID string identifying the submitted job; use with ``get_job`` to track status.
        """

        job_id = str(uuid4())
        self._jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "processed_ids": [],
            "failed_count": 0,
        }
        asyncio.create_task(self._run_reindex_job(job_id=job_id, npc_ids=npc_ids, embedding_index=embedding_index))
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Return a snapshot of a tracked job payload if present.

        Args:
            job_id: UUID string returned by ``submit_reindex``.

        Returns:
            Shallow copy of the job dict, or None if no job with that ID is tracked.
        """

        job = self._jobs.get(job_id)
        return None if job is None else dict(job)

    @property
    def jobs(self) -> dict[str, dict[str, Any]]:
        """Expose internal jobs for focused unit tests."""

        return self._jobs

    async def _run_reindex_job(self, job_id: str, npc_ids: list[str], embedding_index: EmbeddingIndex) -> None:
        """Execute reindex work asynchronously and update job status."""

        job = self._jobs.get(job_id)
        if job is None:
            return

        job["status"] = "running"
        job["started_at"] = datetime.now(timezone.utc).isoformat()
        try:
            for npc_id in npc_ids:
                await embedding_index.invalidate(item_id=npc_id)
            job["status"] = "completed"
            job["processed_ids"] = list(npc_ids)
            job["failed_count"] = 0
        except Exception as error:  # pragma: no cover - exercised by unit tests via stub failures.
            job["status"] = "failed"
            job["error"] = str(error)
            job["failed_count"] = 1
        finally:
            job["finished_at"] = datetime.now(timezone.utc).isoformat()
