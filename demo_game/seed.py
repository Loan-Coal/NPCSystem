"""
Module: seed
Layer: demo_game (external client)
Purpose: Seed the demo world via the NPC Engine HTTP API. STUB — see Phase 2.2.
Dependencies: None (stub only)
Used by: make demo-seed
"""

from __future__ import annotations

import sys


def seed(base_url: str, api_key: str) -> int:
    """Seed the demo world via the NPC Engine API.

    Args:
        base_url: Engine base URL, e.g. http://localhost:8000.
        api_key: Bearer token for authentication.

    Returns:
        Exit code (0 = success, 1 = failure).

    Raises:
        NotImplementedError: This function will be implemented in Phase 2.2.
    """
    raise NotImplementedError("seed() will be implemented in Phase 2.2")


if __name__ == "__main__":
    print("demo_game/seed.py: not yet implemented — see Phase 2.2")
    sys.exit(1)
