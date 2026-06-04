"""
cleanup_scheduler.py - Background scheduler for expired idempotency record cleanup.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: perform request preflight/replay logic.

Dependencies injected: IdempotencyServiceProtocol.
"""

import asyncio

from npc_engine.engines.idempotency.service import IdempotencyServiceProtocol
from npc_engine.utils.logging import get_logger


LOGGER_NAME = "npc_engine.idempotency.cleanup"


class IdempotencyCleanupScheduler:
    """Runs periodic cleanup for expired idempotency records."""

    def __init__(self, service: IdempotencyServiceProtocol, interval_seconds: int) -> None:
        """Initialise the scheduler with a service and polling interval.

        Args:
            service: Idempotency service providing cleanup_expired().
            interval_seconds: Seconds to sleep between cleanup runs (minimum 1).
        """
        self._service = service
        self._interval_seconds = max(1, interval_seconds)
        self._logger = get_logger(LOGGER_NAME)

    async def run_forever(self) -> None:
        """Run the cleanup loop indefinitely until the task is cancelled.

        Logs each cleanup result; swallows non-cancellation exceptions so a
        single backend error cannot stop the scheduler.

        Raises:
            asyncio.CancelledError: Re-raised on task cancellation to allow clean shutdown.
        """
        while True:
            try:
                deleted_count = await self._service.cleanup_expired()
                self._logger.info("idempotency_cleanup_complete", extra={"deleted_count": deleted_count})
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._logger.error("idempotency_cleanup_failed", extra={"error": str(error)})
            await asyncio.sleep(self._interval_seconds)
