"""
test_sev04_events_faction_quest_graph_queries.py
Unit tests verifying SEV-04 migration: events, faction_politics,
and quest_generation Cypher now lives in graph/, not in engines/.

Does NOT: run live Neo4j queries.
Dependencies injected: None (pure import and text inspection).
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parents[2] / "src" / "npc_engine"
_ENGINES = _SRC / "engines"
_GRAPH = _SRC / "graph"


# ---------------------------------------------------------------------------
# Events domain
# ---------------------------------------------------------------------------


def test_event_queries_module_exists() -> None:
    assert (_GRAPH / "event_queries.py").is_file(), "graph/event_queries.py must exist"


def test_event_queries_has_get_characters_at_location() -> None:
    text = (_GRAPH / "event_queries.py").read_text(encoding="utf-8")
    assert "get_characters_at_location" in text


def test_event_queries_seed_awareness_has_is_active_guard() -> None:
    """Awareness seeding must exclude inactive characters."""
    text = (_GRAPH / "event_queries.py").read_text(encoding="utf-8")
    assert "c.is_active = true" in text


def test_event_queries_has_get_locations_by_tag() -> None:
    text = (_GRAPH / "event_queries.py").read_text(encoding="utf-8")
    assert "get_locations_by_tag" in text


def test_event_handler_no_raw_cypher_constants() -> None:
    """event_handler.py must not define inline CYPHER_ constants."""
    text = (_ENGINES / "events" / "event_handler.py").read_text(encoding="utf-8")
    assert "CYPHER_CHARACTERS_AT_LOCATION" not in text
    assert "CYPHER_GET_WORLD_STATE" not in text
    assert "CYPHER_MERGE_WORLD_STATE" not in text


def test_awareness_seeder_no_inline_cypher_run() -> None:
    """awareness_seeder.py was deleted in SEV-24 Wave 5 (dead code); file must not exist."""
    assert not (_ENGINES / "events" / "awareness_seeder.py").exists(), (
        "awareness_seeder.py should have been deleted in SEV-24 Wave 5"
    )


def test_location_scoper_no_inline_cypher_run() -> None:
    """location_scoper.py was deleted in SEV-24 Wave 5 (dead code); file must not exist."""
    assert not (_ENGINES / "events" / "location_scoper.py").exists(), (
        "location_scoper.py should have been deleted in SEV-24 Wave 5"
    )


# ---------------------------------------------------------------------------
# Faction politics domain
# ---------------------------------------------------------------------------


def test_faction_politics_queries_module_exists() -> None:
    assert (_GRAPH / "faction_politics_queries.py").is_file(), (
        "graph/faction_politics_queries.py must exist"
    )


def test_faction_politics_queries_has_required_functions() -> None:
    text = (_GRAPH / "faction_politics_queries.py").read_text(encoding="utf-8")
    assert "get_recent_events" in text
    assert "get_character_factions" in text
    assert "get_all_standings" in text


def test_faction_politics_engine_no_raw_cypher() -> None:
    text = (_ENGINES / "faction_politics" / "faction_politics_engine.py").read_text(encoding="utf-8")
    assert "CYPHER_GET_RECENT_EVENTS" not in text
    assert "CYPHER_GET_CHARACTER_FACTIONS" not in text
    assert "CYPHER_GET_ALL_STANDINGS" not in text


# ---------------------------------------------------------------------------
# Quest generation domain
# ---------------------------------------------------------------------------


def test_quest_generation_queries_module_exists() -> None:
    assert (_GRAPH / "quest_generation_queries.py").is_file(), (
        "graph/quest_generation_queries.py must exist"
    )


def test_quest_generation_queries_has_required_functions() -> None:
    text = (_GRAPH / "quest_generation_queries.py").read_text(encoding="utf-8")
    assert "get_character_info" in text
    assert "get_candidate_ids_by_label" in text
    assert "check_node_labels" in text
    assert "get_template_skill_requirements" in text


def test_quest_generation_engine_no_raw_cypher() -> None:
    text = (_ENGINES / "quest_generation" / "quest_generation_engine.py").read_text(encoding="utf-8")
    assert "_CYPHER_GET_CHARACTER" not in text
    assert "_CYPHER_GET_NODES_BY_TYPE" not in text


def test_slot_validator_no_raw_cypher() -> None:
    text = (_ENGINES / "quest_generation" / "slot_validator.py").read_text(encoding="utf-8")
    assert "_CYPHER_CHECK_NODE" not in text
    assert "_CYPHER_TEMPLATE_SKILL_REQS" not in text
