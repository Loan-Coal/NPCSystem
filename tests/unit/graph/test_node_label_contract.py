"""
test_node_label_contract.py - Contract tests binding resolve_node_label to the labels
graph/'s hand-written Cypher actually reads and writes (M1.2, ISSUE-213).

The generic write path (generic_node_service -> resolve_node_label) and the hand-written
Cypher in graph/ are two writers over one database. When they disagree, the graph grows a
lowercase duplicate of a PascalCase label (measured live: Belief 44 / belief 1, need 28 /
Need 0). Every expected value below is curated from the query file that owns the label, and
cited on its row; that citation is the contract.

Does NOT: touch a real Neo4j database or read any YAML through a fixture (the loader reads
the shipped package files directly, which is the behaviour under test).

Dependencies injected: None.
"""

from __future__ import annotations

import pytest

from npc_engine.graph.generic.generic_graph_utils import BASE_NODE_LABELS, resolve_node_label
from npc_engine.type_registry.base_contract_loader import load_base_node_types

# Every base node kind mapped to the label graph/'s hand-written Cypher uses, with the
# file:line that witnesses it. Sorted by key. `choice` is the single kind with no witness
# anywhere in graph/ (no `:Choice` in any Cypher, no Python reference at all) — it is
# PascalCase by naming convention only, and marked as such rather than cited.
EXPECTED_NODE_LABELS: dict[str, str] = {
    "agenda": "Agenda",  # graph/political/political_agenda_writer.py:18
    "army": "Army",  # graph/military/military_queries.py:33
    "belief": "Belief",  # graph/knowledge/belief_queries.py:22
    "chapter": "Chapter",  # graph/narrative/chapter_queries.py:22
    "character": "Character",  # graph/character/character_reader.py:28
    "choice": "Choice",  # no graph/ witness; PascalCase by convention
    "deduction": "Deduction",  # graph/intrigue/investigation_queries.py:86
    "dialogue_turn": "DialogueTurn",  # graph/infra/session_persistence.py:31
    "event": "Event",  # graph/economy/pricing_queries.py:23
    "evidence": "Evidence",  # graph/intrigue/investigation_queries.py:24
    "faction": "Faction",  # graph/economy/pricing_queries.py:29
    "faction_standing_event": "FactionStandingEvent",  # graph/faction/faction_history_queries.py:22
    "goal": "Goal",  # graph/group/group_queries.py:91
    "group": "Group",  # graph/group/group_queries.py:22
    "item": "Item",  # graph/economy/item_queries.py:22
    "leverage": "Leverage",  # graph/political/political_leverage_writer.py:18
    "location": "Location",  # graph/economy/pricing_queries.py:18
    "memory": "Memory",  # graph/memory/memory_queries.py:21
    "narrative_beat": "NarrativeBeat",  # graph/narrative/chapter_queries.py:62
    "need": "Need",  # graph/intent/intent_queries.py:38
    "pending_intent": "PendingIntent",  # graph/intent/intent_queries.py:60
    "player_model": "PlayerModel",  # graph/character/player_model_writer.py:24
    "quest": "Quest",  # graph/character/skill_queries.py:77
    "quest_template": "QuestTemplate",  # graph/character/skill_queries.py:79
    "resource_node": "ResourceNode",  # graph/military/military_control_writer.py:34
    "rumor": "Rumor",  # graph/gossip/rumor_queries.py:22
    "schedule": "Schedule",  # graph/scheduling/routine_queries.py:26
    "scheme": "Scheme",  # graph/intrigue/scheme_reader.py:35
    "secret": "Secret",  # graph/group/group_queries.py:84
    "skill": "Skill",  # graph/character/skill_queries.py:28
    "title": "Title",  # graph/political/political_queries.py:27
    "trait": "Trait",  # graph/character/trait_queries.py:22
    "treaty": "Treaty",  # graph/political/treaty_queries.py:17
    "world_state": "WorldState",  # graph/world_state/world_state_reader.py:25
}


@pytest.mark.parametrize(("node_key", "expected_label"), sorted(EXPECTED_NODE_LABELS.items()))
def test_resolve_node_label_matches_hand_written_cypher(node_key: str, expected_label: str) -> None:
    """resolve_node_label must return the same label graph/'s own Cypher uses.

    A disagreement here is what mints a lowercase duplicate label in Neo4j: the generic
    write path creates `(:belief)` while belief_queries.py reads `(:Belief)`.
    """

    assert resolve_node_label(node_key) == expected_label


def test_expected_labels_cover_every_shipped_base_node_kind() -> None:
    """The curated table must not silently fall behind base_nodes/*.yaml.

    A new base node contract that nobody adds a row for would otherwise be unprotected by
    the parametrised test above.
    """

    assert set(load_base_node_types()) == set(EXPECTED_NODE_LABELS)


@pytest.mark.parametrize(("node_key", "expected_label"), sorted(BASE_NODE_LABELS.items()))
def test_base_node_labels_map_still_wins(node_key: str, expected_label: str) -> None:
    """Regression guard: the seven hardcoded base kinds keep resolving PascalCase.

    Passes today and must keep passing. BASE_NODE_LABELS is consulted first precisely so a
    YAML file that regresses to a lowercase `node_type:` cannot break the base kinds — the
    inversion ISSUE-213 originally prescribed, which would have resolved
    character -> "character" and 404'd every eval case at evals/runner.py:97.
    """

    assert resolve_node_label(node_key) == expected_label
