"""
Package: story_pacing
Layer: engines
Purpose: Meta-engine that gates other engines by writing pacing multipliers to WorldState each tick.
Does NOT: call LLMs, create graph nodes, or expose HTTP routes.
Dependencies injected: none at package level; see submodules.
Public surface: StoryPacingEngine, PacingRules, load_pacing_rules
"""

from __future__ import annotations
