"""
Package: planning
Layer: engines
Purpose: Lightweight GOAP-style planning engine — reads NPC needs, forms goals, and
         dispatches move actions when goal urgency exceeds the routine priority threshold.
Does NOT: call LLMs, open transactions, or import from api/ or services/.
Dependencies injected: None at package level; individual classes accept AsyncSession per call.
Public surface: GoalFormer, ActionSelector, action_priority constants.
"""

from __future__ import annotations
