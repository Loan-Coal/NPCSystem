"""
Package: planning
Layer: engines
Purpose: Lightweight GOAP-style planning engine — reads NPC needs, forms goals, and
         dispatches move actions when goal urgency exceeds the routine priority threshold.
Does NOT: call LLMs, open transactions, hold a session, or import from api/, services/,
          or the graph layer.
Dependencies injected: None at package level; individual classes take a PlanningGraphPort
                       (DEC-122 / SEV-24) via __init__.
Public surface: GoalFormer, ActionSelector, action_priority constants.
"""

from __future__ import annotations
