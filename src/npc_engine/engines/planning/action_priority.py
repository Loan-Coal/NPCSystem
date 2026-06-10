"""
Module: action_priority
Layer: engines
Purpose: Named integer constants for the 0-100 action priority system (DEC-083).
         Engines compare goal urgency against these thresholds — never raw integers.
Dependencies: None (pure constants module).
Used by: npc_engine.engines.planning.goal_former,
         npc_engine.engines.planning.action_selector
Does NOT: contain logic, import from any other module, or instantiate objects.
Dependencies injected: None.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Priority thresholds
# ---------------------------------------------------------------------------

ROUTINE_PRIORITY: int = 50
"""Goals at or below this urgency defer to the routine engine."""

GOAL_CRITICAL: int = 90
"""Goals at this urgency or above are life-threatening / survival-critical."""

GOAL_HIGH: int = 75
"""Goals in the high band — urgent but not critical."""

GOAL_NORMAL: int = 50
"""Goals at the boundary with routine priority — equivalent weight."""

GOAL_LOW: int = 25
"""Goals below routine priority — background desires that do not override movement."""

# ---------------------------------------------------------------------------
# Urgency computation helpers
# ---------------------------------------------------------------------------

MAX_URGENCY: int = 100
"""Hard ceiling for urgency values."""

MIN_NEED_LEVEL: int = 0
"""Minimum valid need level (fully depleted)."""
