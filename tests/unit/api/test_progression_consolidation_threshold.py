"""
test_progression_consolidation_threshold.py - The consolidation factory reads its threshold from config.

T25.6: the engine was built with a hard-coded turn_threshold=5 while
CONSOLIDATION_TURN_THRESHOLD was read only by the dashboard (rule 3, one source).

Does NOT: build a real LLM client, open Neo4j, or read prompt files.
Dependencies injected: module-level factory collaborators patched with mocks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

_PROGRESSION = "npc_engine.api.dependencies_advanced.progression"
_ENGINE_CLS = (
    "npc_engine.engines.memory_consolidation.memory_consolidation_engine.MemoryConsolidationEngine"
)
_REPO_CLS = (
    "npc_engine.graph.repositories.memory_consolidation_repository.Neo4jMemoryConsolidationRepository"
)


def _build_with_threshold(threshold: int) -> MagicMock:
    """Call the uncached factory with settings carrying ``threshold``; return the engine mock."""
    from npc_engine.api.dependencies_advanced.progression import get_memory_consolidation_engine

    settings = MagicMock()
    settings.CONSOLIDATION_TURN_THRESHOLD = threshold
    with (
        patch(f"{_PROGRESSION}.get_settings", return_value=settings),
        patch(f"{_PROGRESSION}.get_engine_model_config_for", return_value=MagicMock()),
        patch(f"{_PROGRESSION}.create_llm_client_for_engine", return_value=MagicMock()),
        patch(f"{_PROGRESSION}._register_adapter", side_effect=lambda client: client),
        patch(f"{_PROGRESSION}.get_session_store", return_value=MagicMock()),
        patch(f"{_PROGRESSION}.get_graph_db", return_value=MagicMock()),
        patch(_REPO_CLS),
        patch(_ENGINE_CLS) as engine_cls,
    ):
        get_memory_consolidation_engine.__wrapped__()
    return engine_cls


def test_factory_passes_configured_turn_threshold() -> None:
    """The engine's turn_threshold is CONSOLIDATION_TURN_THRESHOLD, whatever its value."""
    for threshold in (3, 10):
        engine_cls = _build_with_threshold(threshold)
        assert engine_cls.call_args.kwargs["turn_threshold"] == threshold
