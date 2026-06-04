"""
Regression tests for SEV-04 domain migrations: routine and skill.

Confirms that:
- graph.routine_queries exposes the expected async query functions
- graph.skill_queries exposes get_completed_quests_with_skills
- engines/skill/skill_progression_engine does NOT call session.run directly
  (all Cypher routed through graph/)
"""
from __future__ import annotations

import inspect


def test_graph_routine_queries_module_importable() -> None:
    """graph.routine_queries must exist and export the four query functions."""
    from npc_engine.graph import routine_queries  # noqa: F401 - import is the assertion
    assert hasattr(routine_queries, "get_scheduled_characters")
    assert hasattr(routine_queries, "update_character_location")
    assert hasattr(routine_queries, "clear_routine_override")
    assert hasattr(routine_queries, "set_routine_override")


def test_graph_routine_queries_functions_are_async() -> None:
    """All four routine query helpers must be coroutine functions."""
    from npc_engine.graph import routine_queries

    for name in (
        "get_scheduled_characters",
        "update_character_location",
        "clear_routine_override",
        "set_routine_override",
    ):
        fn = getattr(routine_queries, name)
        assert inspect.iscoroutinefunction(fn), f"{name} must be async"


def test_graph_skill_queries_has_completed_quests_function() -> None:
    """graph.skill_queries must expose get_completed_quests_with_skills."""
    from npc_engine.graph import skill_queries  # noqa: F401
    assert hasattr(skill_queries, "get_completed_quests_with_skills")
    assert inspect.iscoroutinefunction(skill_queries.get_completed_quests_with_skills)


def test_skill_progression_engine_no_direct_session_run() -> None:
    """SkillProgressionEngine.run_tick must delegate to graph/ not call session.run."""
    import ast
    import pathlib

    src = pathlib.Path(
        "src/npc_engine/engines/skill/skill_progression_engine.py"
    ).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "run":
            # Any `<expr>.run(...)` where the caller looks like `session`
            if isinstance(node.value, ast.Name) and node.value.id == "session":
                raise AssertionError(
                    "skill_progression_engine must not call session.run() directly"
                )
