"""
test_graph_admin_reindex_jobs.py - Unit tests for async reindex job lifecycle.

Does NOT: verify vector embedding quality.

Dependencies injected: None.
"""

import pytest
from typing import cast

from npc_engine.retrieval.reindex_job_service import ReindexJobService
from npc_engine.retrieval.embedding_index import EmbeddingIndex


class _EmbeddingIndexStub:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.invalidated: list[str] = []

    async def invalidate(self, item_id: str) -> None:
        if self.should_fail:
            raise RuntimeError("reindex failed")
        self.invalidated.append(item_id)


@pytest.mark.asyncio
async def test_run_reindex_job_marks_completed() -> None:
    """Background reindex worker should move job to completed state on success."""

    service = ReindexJobService()
    service.jobs["job-1"] = {"job_id": "job-1", "status": "queued", "processed_ids": [], "failed_count": 0}
    index = _EmbeddingIndexStub(should_fail=False)

    await service._run_reindex_job(
        job_id="job-1",
        npc_ids=["a", "b"],
        embedding_index=cast(EmbeddingIndex, index),
    )

    job = service.jobs["job-1"]
    assert job["status"] == "completed"
    assert job["processed_ids"] == ["a", "b"]
    assert job["failed_count"] == 0
    assert index.invalidated == ["a", "b"]


@pytest.mark.asyncio
async def test_run_reindex_job_marks_failed_on_error() -> None:
    """Background reindex worker should move job to failed state when invalidation fails."""

    service = ReindexJobService()
    service.jobs["job-2"] = {"job_id": "job-2", "status": "queued", "processed_ids": [], "failed_count": 0}
    index = _EmbeddingIndexStub(should_fail=True)

    await service._run_reindex_job(
        job_id="job-2",
        npc_ids=["a"],
        embedding_index=cast(EmbeddingIndex, index),
    )

    job = service.jobs["job-2"]
    assert job["status"] == "failed"
    assert job["failed_count"] == 1
    assert "error" in job
