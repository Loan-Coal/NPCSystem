"""
Package: engines.routine
Layer: engines
Purpose: Tick-driven NPC location engine that moves characters according to their schedules.
Does NOT: define scheduling intervals or read world state directly.
Dependencies injected: None (RoutineEngine is constructed without arguments).
Public surface: RoutineEngine
"""

from __future__ import annotations
