"""
Package: skill
Layer: engines
Purpose: Engine for awarding XP and levelling character skills after quest completion.
Does NOT: call LLMs or modify skill definitions.
Dependencies injected: SkillGraphPort (via SkillProgressionEngine __init__).
Public surface: SkillProgressionEngine
"""

from __future__ import annotations
