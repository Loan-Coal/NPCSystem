"""
redis_runtime.py - Optional Redis runtime integration for non-idempotency caches.
Layer: services
Purpose: (auto-detected — review)

Does NOT: participate in idempotency replay decisions.

Dependencies injected: Settings.
"""

from __future__ import annotations

from typing import Any

from npc_engine.config import Settings
from npc_engine.utils.logging import get_logger


LOGGER_NAME = "npc_engine.redis"


class RedisRuntime:
    """Manages optional Redis connection lifecycle for cache features."""

    def __init__(self, settings: Settings) -> None:
        """Initialize Redis runtime with application settings.

        Args:
            settings: Application settings used to configure Redis URL and timeouts.
        """
        self._settings = settings
        self._logger = get_logger(LOGGER_NAME)
        self._client: Any = None

    async def connect(self) -> None:
        """Attempt Redis connection when enabled; degrade gracefully on failures."""

        if not self._settings.REDIS_ENABLED:
            return

        try:
            from redis.asyncio import Redis

            self._client = Redis.from_url(
                self._settings.REDIS_URL,
                socket_connect_timeout=self._settings.REDIS_CONNECT_TIMEOUT_SECONDS,
                decode_responses=True,
            )
            await self._client.ping()
            self._logger.info("redis_connected")
        except Exception as error:
            self._client = None
            self._logger.warning("redis_unavailable", extra={"error": str(error)})

    async def close(self) -> None:
        """Close Redis client when available."""

        if self._client is None:
            return

        await self._client.aclose()
        self._client = None

    @property
    def is_available(self) -> bool:
        """Return True when Redis client is connected and available."""

        return self._client is not None
