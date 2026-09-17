"""
Regression tests for SEV-04 domain migrations: routine and skill graph layer.

Confirms that:
- graph.routine_queries exposes the expected async query functions
- graph.skill_queries exposes get_completed_quests_with_skills
"""
from __future__ import annotations

import inspect


def test_graph_routine_queries_module_importable() -> None:
    """graph.routine_queries must exist and export the four query functions."""
    from npc_engine.graph.scheduling import routine_queries  # noqa: F401 - import is the assertion
    assert hasattr(routine_queries, "get_scheduled_characters")
    assert hasattr(routine_queries, "update_character_location")
    assert hasattr(routine_queries, "clear_routine_override")
    assert hasattr(routine_queries, "set_routine_override")


def test_graph_routine_queries_functions_are_async() -> None:
    """All four routine query helpers must be coroutine functions."""
    from npc_engine.graph.scheduling import routine_queries

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
    from npc_engine.graph.character import skill_queries  # noqa: F401
    assert hasattr(skill_queries, "get_completed_quests_with_skills")
    assert inspect.iscoroutinefunction(skill_queries.get_completed_quests_with_skills)


