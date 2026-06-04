"""
test_architecture_conformance.py - Enforces core architecture constraints.

Does NOT: validate runtime business behavior.

Dependencies injected: None.
"""

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2] / "src" / "npc_engine"
EXCLUDED_PATH_PARTS = {
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".tox",
    "site-packages",
    "Lib",
    "Scripts",
}


def _python_files() -> list[Path]:
    return [
        path
        for path in PROJECT_ROOT.rglob("*.py")
        if all(part not in EXCLUDED_PATH_PARTS for part in path.parts)
    ]


def test_all_python_files_have_module_docstring_contract() -> None:
    """Every module must include scope and dependency docstring fields."""

    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        assert text.startswith('"""'), f"Missing module docstring in {path}"
        assert "Does NOT:" in text, f"Missing scope boundary in {path}"
        assert "Dependencies injected:" in text, f"Missing dependency declaration in {path}"


def test_no_wildcard_imports() -> None:
    """Wildcard imports are banned across the codebase."""

    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        wildcard_import_pattern = re.compile(r"^\s*(from\s+\S+\s+import\s+\*)", re.MULTILINE)
        assert wildcard_import_pattern.search(text) is None, f"Wildcard import found in {path}"


def test_engines_do_not_import_concrete_llm_adapters() -> None:
    """Engine modules must depend on abstractions, not concrete adapters."""

    engines_dir = PROJECT_ROOT / "engines"
    if not engines_dir.exists():
        return

    for path in engines_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name == "factory.py":
            continue
        if path.parent.name == "llm" and path.name.endswith("_adapter.py"):
            continue
        banned_imports = (
            "mistral_adapter",
            "llama_adapter",
            "openai_adapter",
        )
        for banned_import in banned_imports:
            assert banned_import not in text, f"Concrete adapter import found in {path}"


def test_gossip_pair_selector_query_requires_active_characters() -> None:
    """Gossip pair selection query must exclude inactive characters (SEV-04: now in graph layer)."""

    # After SEV-04 the CYPHER_GOSSIP_PAIRS query lives in graph/gossip_queries.py.
    gossip_queries_path = PROJECT_ROOT / "graph" / "gossip_queries.py"
    gossip_queries_text = gossip_queries_path.read_text(encoding="utf-8")

    assert "a.is_active = true" in gossip_queries_text
    assert "b.is_active = true" in gossip_queries_text


def test_awareness_seeder_query_requires_active_characters() -> None:
    """Awareness seeding query must exclude inactive characters."""

    awareness_seeder_path = PROJECT_ROOT / "engines" / "events" / "awareness_seeder.py"
    awareness_seeder_text = awareness_seeder_path.read_text(encoding="utf-8")

    assert "c.is_active = true" in awareness_seeder_text


def test_dialogue_stream_path_includes_emotion_state_in_context_builder_call() -> None:
    """Stream dialogue path should include emotion state in context assembly."""

    dialogue_handler_path = PROJECT_ROOT / "engines" / "dialogue" / "dialogue_handler.py"
    dialogue_handler_text = dialogue_handler_path.read_text(encoding="utf-8")

    assert "async def stream" in dialogue_handler_text
    assert "emotion_state={\"current_mood\": current_emotion.label}" in dialogue_handler_text


def test_gossip_and_event_handlers_use_shared_safe_invalidation_helper() -> None:
    """Engine handlers should use the shared safe invalidation helper."""

    gossip_handler_path = PROJECT_ROOT / "engines" / "gossip" / "gossip_handler.py"
    event_handler_path = PROJECT_ROOT / "engines" / "events" / "event_handler.py"

    gossip_text = gossip_handler_path.read_text(encoding="utf-8")
    event_text = event_handler_path.read_text(encoding="utf-8")

    assert "invalidate_embedding_safely" in gossip_text
    assert "invalidate_embedding_safely" in event_text
