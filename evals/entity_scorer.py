"""
Module: entity_scorer
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Pure unsupported-entity rate scorer. Uses alias-table whole-word matching
         (not NER) to detect entity mentions in text, then reports the fraction of
         mentions that resolve to entity IDs absent from the graph vocabulary.
Dependencies: pydantic v2, re, pathlib, yaml, graph_vocabulary (evals/)
Used by: evals.deterministic_pass

Scope and documented limits:
- Pronouns are invisible — only aliases listed in the table are detectable.
- Partial names ("the Captain") require an explicit entry in the alias table.
- Unnamed fabrications ("a merchant from the eastern docks") are undetectable.
- Matching is whole-word (\\b boundaries) and case-insensitive.
- Multi-word aliases are matched before their single-word substrings (longest first)
  so "the Captain" never double-counts the lone "Captain" alias.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from graph_vocabulary import GraphVocabulary

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RATE_DECIMALS: int = 3

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AliasTable(BaseModel):
    """Mapping from text strings to canonical entity IDs.

    Keys are text patterns (e.g. "the Captain", "mira_innkeeper") that may
    appear in generated NPC dialogue. Values are canonical graph node IDs.

    Frozen to ensure immutability after construction.

    Attributes:
        aliases: Dict mapping alias string → canonical entity node ID.
    """

    model_config = ConfigDict(frozen=True)

    aliases: dict[str, str]


class EntityScore(BaseModel):
    """Result of the unsupported-entity rate scorer.

    Attributes:
        mentions: Total alias matches found in the text (each match = one mention).
        unsupported: Mentions whose canonical ID is absent from the vocabulary.
        rate: unsupported / mentions, rounded to 3 decimal places; 0.0 when
              mentions == 0 (no division-by-zero).
    """

    model_config = ConfigDict(frozen=True)

    mentions: int
    unsupported: int
    rate: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compile_patterns(aliases: dict[str, str]) -> list[tuple[re.Pattern[str], str]]:
    """Compile alias strings into whole-word regex patterns, longest first.

    Sorting by descending length ensures multi-word aliases (e.g. "the Captain")
    are matched and blanked out before their single-word substrings ("Captain"),
    preventing double-counting.

    Args:
        aliases: Raw alias dict — alias text → canonical entity ID.
    Returns:
        List of (compiled regex, canonical_id) sorted longest alias first.
    """
    sorted_pairs = sorted(aliases.items(), key=lambda kv: -len(kv[0]))
    return [
        (re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE), canonical_id)
        for alias, canonical_id in sorted_pairs
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_aliases(path: Path) -> AliasTable:
    """Load an AliasTable from a YAML file.

    The YAML file must contain a top-level ``aliases`` mapping of
    text string → canonical entity ID.

    Args:
        path: Path to the alias YAML file.
    Returns:
        Validated, frozen AliasTable.
    Raises:
        FileNotFoundError: If the path does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        pydantic.ValidationError: If the YAML structure does not match AliasTable.
    """
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AliasTable.model_validate(data)


def unsupported_entity_rate(
    text: str,
    vocabulary: GraphVocabulary,
    aliases: AliasTable,
) -> EntityScore:
    """Return the fraction of detected entity mentions not in the vocabulary.

    Uses alias-table whole-word matching (not NER). Pronouns are invisible — only
    strings present in the alias table are detectable as entity references. Each
    non-overlapping match of an alias in the text counts as one mention.

    Algorithm:
    1. Compile aliases into whole-word regex patterns (longest alias first).
    2. Scan text with each pattern; collect canonical IDs for every match.
    3. After each pattern matches, blank out those spans to prevent double-counting.
    4. Count how many canonical IDs are absent from vocabulary.ids.
    5. Return EntityScore with totals and rounded rate.

    Args:
        text: NPC generated dialogue or response text.
        vocabulary: Frozen graph vocabulary containing all known entity node IDs.
        aliases: Alias table mapping text strings to canonical entity node IDs.
    Returns:
        EntityScore with mention count, unsupported count, and rate.
    """
    patterns = _compile_patterns(aliases.aliases)
    remaining = text
    mention_ids: list[str] = []

    for pattern, canonical_id in patterns:
        matches = pattern.findall(remaining)
        if matches:
            mention_ids.extend([canonical_id] * len(matches))
            remaining = pattern.sub(" ", remaining)

    mentions = len(mention_ids)
    unsupported = sum(1 for cid in mention_ids if cid not in vocabulary.ids)
    rate = round(unsupported / mentions, _RATE_DECIMALS) if mentions > 0 else 0.0

    return EntityScore(mentions=mentions, unsupported=unsupported, rate=rate)
