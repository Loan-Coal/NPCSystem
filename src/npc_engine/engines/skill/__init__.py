"""
Package: skill
Layer: engines
Purpose: Engine for awarding XP and levelling character skills after quest completion.
Does NOT: call LLMs or modify skill definitions.
Dependencies injected: AsyncSession (via run_tick).
Public surface: SkillProgressionEngine
"""
