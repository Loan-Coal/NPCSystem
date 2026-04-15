"""
base_engine.py - Defines a minimal asynchronous engine contract.

Does NOT: implement domain-specific engine behavior.

Dependencies injected: None.
"""

from typing import Protocol


class BaseEngine(Protocol):
    """Protocol for tick-driven engines."""

    async def tick(self, tick_id: int) -> None:
        """Execute one engine tick."""
