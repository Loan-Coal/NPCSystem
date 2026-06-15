"""
Package: oath
Layer: engines
Purpose: Engine for managing pledge lifecycle — expiry and violation detection.
Does NOT: call LLMs or modify pledge terms.
Dependencies injected: AsyncSession (via run_tick).
Public surface: OathEngine
"""

from __future__ import annotations
