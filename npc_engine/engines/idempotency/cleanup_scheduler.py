"""
cleanup_scheduler.py - Background scheduler for expired idempotency record cleanup.

Does NOT: perform request preflight/replay logic.

Dependencies injected: IdempotencyServiceProtocol.
"""

import asyncio

from engines.idempotency.service import IdempotencyServiceProtocol
from utils.logging import get_logger


LOGGER_NAME = "npc_engine.idempotency.cleanup"


class IdempotencyCleanupScheduler:
    """Runs periodic cleanup for expired idempotency records."""

    def __init__(self, service: IdempotencyServiceProtocol, interval_seconds: int):
        self._service = service
        self._interval_seconds = max(1, interval_seconds)
        self._logger = get_logger(LOGGER_NAME)

    async def run_forever(self) -> None:
        """Run cleanup loop until cancelled."""

        while True:
            try:
                deleted_count = await self._service.cleanup_expired()
                self._logger.info("idempotency_cleanup_complete", extra={"deleted_count": deleted_count})
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._logger.error("idempotency_cleanup_failed", extra={"error": str(error)})
            await asyncio.sleep(self._interval_seconds)
