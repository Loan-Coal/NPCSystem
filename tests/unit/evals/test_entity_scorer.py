"""
Module: test_entity_scorer
Layer: test (unit)
Purpose: Tests for evals/entity_scorer.py — pure alias-table whole-word matching,
         unsupported-entity counting, and rate computation. Zero I/O; all tests use
         inline AliasTable and GraphVocabulary instances.
Dependencies: pytest, entity_scorer (evals/), graph_vocabulary (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from entity_scorer import AliasTable, EntityScore, load_aliases, unsupported_entity_rate
from graph_vocabulary import GraphVocabulary

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_DEMO_VOCAB = GraphVocabulary(ids=frozenset({"mira_innkeeper", "captain_sorn"}))

_DEMO_ALIASES = AliasTable(
    aliases={
        "mira_innkeeper": "mira_innkeeper",
        "the Captain": "captain_sorn",
        "Captain": "captain_sorn",
        "Warden Aldous": "warden_aldous",  # absent from vocab
    }
)

# Text naming three entities: mira_innkeeper (known), the Captain (alias→known),
# Warden Aldous (alias→absent).
_FIXTURE_TEXT = (
    "mira_innkeeper greeted us warmly. The Captain confirmed the news. "
    "Warden Aldous denied everything."
)

# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_unknown_proper_noun_counts_as_unsupported() -> None:
    """Alias resolving to an ID absent from vocabulary is counted as unsupported."""
    result = unsupported_entity_rate(_FIXTURE_TEXT, _DEMO_VOCAB, _DEMO_ALIASES)
    assert result.mentions == 3
    assert result.unsupported == 1
    assert result.rate == 0.333


# ---------------------------------------------------------------------------
# Pronoun scope
# ---------------------------------------------------------------------------


def test_pronoun_only_sentence_has_zero_mentions() -> None:
    """Pronouns are out of scope — they must not be counted as entity mentions."""
    text = "She told him that they would not do it. He said nothing."
    result = unsupported_entity_rate(text, _DEMO_VOCAB, _DEMO_ALIASES)
    assert result.mentions == 0


# ---------------------------------------------------------------------------
# Rate edge cases
# ---------------------------------------------------------------------------


def test_rate_is_zero_when_no_mentions() -> None:
    """Zero mentions → rate 0.0, not a division error."""
    result = unsupported_entity_rate("No entities here.", _DEMO_VOCAB, _DEMO_ALIASES)
    assert result.rate == 0.0
    assert result.mentions == 0
    assert result.unsupported == 0


def test_rate_is_zero_when_all_mentions_known() -> None:
    """All mentions resolve to known IDs → unsupported 0, rate 0.0."""
    text = "mira_innkeeper spoke with the Captain at length."
    result = unsupported_entity_rate(text, _DEMO_VOCAB, _DEMO_ALIASES)
    assert result.mentions == 2
    assert result.unsupported == 0
    assert result.rate == 0.0


def test_rate_is_one_when_all_mentions_unsupported() -> None:
    """All mentions resolve to absent IDs → rate 1.0."""
    text = "Warden Aldous commanded the district."
    result = unsupported_entity_rate(text, _DEMO_VOCAB, _DEMO_ALIASES)
    assert result.mentions == 1
    assert result.unsupported == 1
    assert result.rate == 1.0


# ---------------------------------------------------------------------------
# Case-insensitivity
# ---------------------------------------------------------------------------


def test_matching_is_case_insensitive() -> None:
    """Aliases match regardless of capitalisation in the text."""
    text = "MIRA_INNKEEPER was there."
    result = unsupported_entity_rate(text, _DEMO_VOCAB, _DEMO_ALIASES)
    assert result.mentions == 1
    assert result.unsupported == 0


# ---------------------------------------------------------------------------
# Multi-word aliases prevent double-counting
# ---------------------------------------------------------------------------


def test_multi_word_alias_not_double_counted() -> None:
    """'the Captain' as a two-word alias must not also match the lone 'Captain' alias."""
    text = "The Captain arrived."
    aliases = AliasTable(
        aliases={
            "the Captain": "captain_sorn",
            "Captain": "captain_sorn",
        }
    )
    result = unsupported_entity_rate(text, _DEMO_VOCAB, aliases)
    assert result.mentions == 1


# ---------------------------------------------------------------------------
# EntityScore model
# ---------------------------------------------------------------------------


def test_entity_score_is_frozen() -> None:
    """EntityScore is immutable after construction."""
    score = EntityScore(mentions=1, unsupported=0, rate=0.0)
    # quality-ok: the assertion is 'any mutation is rejected' and the two model families raise different types (pydantic v2 frozen -> ValidationError, frozen dataclass -> FrozenInstanceError); narrowing per-site is deferred, see ISSUES
    with pytest.raises(Exception):
        score.mentions = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# load_aliases
# ---------------------------------------------------------------------------


def test_load_aliases_reads_yaml(tmp_path: pytest.TempPathFactory) -> None:
    """load_aliases deserialises a YAML file into a frozen AliasTable."""
    yaml_content = "aliases:\n  mira_innkeeper: mira_innkeeper\n  Captain: captain_sorn\n"
    alias_file = tmp_path / "aliases.yaml"
    alias_file.write_text(yaml_content, encoding="utf-8")
    table = load_aliases(alias_file)
    assert table.aliases["mira_innkeeper"] == "mira_innkeeper"
    assert table.aliases["Captain"] == "captain_sorn"
    assert isinstance(table, AliasTable)
