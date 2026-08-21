"""
Module: deterministic_pass
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Wires the entity and knowledge scorers into a single offline scoring pass
         over a cached transcript. Accepts a GenerationRecord sequence and pre-loaded
         vocabulary artifacts; emits aggregate entity-rate and knowledge-rate with no
         network calls to Ollama or any LLM backend.
Dependencies: entity_scorer, knowledge_scorer, graph_vocabulary, eval_records,
              pydantic v2, argparse, pathlib, sys, typing
Used by: make eval-score (CLI entry point); tests/unit/evals/test_deterministic_pass.py

Documented scope:
- Entity scoring: whole-word alias-table matching; pronouns and unnamed fabrications
  are undetectable (see entity_scorer module docstring for complete limits).
- Knowledge scoring: whole-word event-ID matching; beliefs, goals, memories, and
  WITNESSED edges are excluded from npc_known_event_ids (see knowledge_scorer module
  docstring for false-positive risk).
- No LLM calls: safe to run with Ollama down. HTTP vocabulary fetch belongs in
  graph_vocabulary.fetch_vocabulary; this module only consumes pre-loaded artifacts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict

from entity_scorer import AliasTable, EntityScore, load_aliases, unsupported_entity_rate
from eval_records import GenerationRecord, read_transcript
from graph_vocabulary import GraphVocabulary
from knowledge_scorer import KnowledgeScore, unpropagated_references

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_ALIASES_PATH: Path = Path(__file__).resolve().parent / "cases" / "entity_aliases.yaml"
_RATE_DECIMALS: int = 3

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RecordScore(BaseModel):
    """Per-record scoring result from the deterministic pass.

    Attributes:
        record_id: Stable identifier from the source GenerationRecord.
        entity: Entity-rate score for this record's npc_response.
        knowledge: Knowledge-violation score for this record's npc_response.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    entity: EntityScore
    knowledge: KnowledgeScore


class DeterministicPassResult(BaseModel):
    """Aggregate result of a deterministic scoring pass over a transcript.

    Rates use a pooled denominator: total_unsupported / total_mentions (entity)
    and total_violations / total_references (knowledge). Both default to 0.0
    when their denominator is zero across the entire transcript.

    Attributes:
        record_count: Number of GenerationRecords scored.
        entity_rate: Pooled unsupported-entity rate across all records.
        knowledge_rate: Pooled knowledge-violation rate across all records.
        record_scores: Per-record entity and knowledge breakdown.
    """

    model_config = ConfigDict(frozen=True)

    record_count: int
    entity_rate: float
    knowledge_rate: float
    record_scores: tuple[RecordScore, ...]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_transcript(
    records: Sequence[GenerationRecord],
    vocabulary: GraphVocabulary,
    aliases: AliasTable,
    event_vocabulary: frozenset[str],
    npc_known_events: dict[str, frozenset[str]],
) -> DeterministicPassResult:
    """Score all records using entity and knowledge scorers; no LLM calls.

    Each record's npc_response is scored independently; results are pooled into
    aggregate entity_rate and knowledge_rate. For entity scoring, IDs absent from
    *vocabulary* count as unsupported mentions. For knowledge scoring, event IDs
    absent from the NPC's entry in *npc_known_events* count as violations; NPCs
    with no entry are treated as knowing nothing.

    Args:
        records: Ordered sequence of GenerationRecords to score.
        vocabulary: Pre-loaded graph vocabulary for entity scoring.
        aliases: Pre-loaded alias table mapping text strings to canonical entity IDs.
        event_vocabulary: Set of all event node IDs to search for in text.
        npc_known_events: Mapping npc_id → frozenset of event IDs the NPC may
            reference without violation. Missing npc_ids default to empty set.
    Returns:
        Frozen DeterministicPassResult with per-record and aggregate scores.
    """
    record_scores: list[RecordScore] = []
    total_mentions: int = 0
    total_unsupported: int = 0
    total_references: int = 0
    total_violations: int = 0

    for record in records:
        known: frozenset[str] = npc_known_events.get(record.npc_id, frozenset())
        entity_score: EntityScore = unsupported_entity_rate(
            record.npc_response, vocabulary, aliases
        )
        knowledge_score: KnowledgeScore = unpropagated_references(
            record.npc_response, event_vocabulary, known
        )
        record_scores.append(
            RecordScore(
                record_id=record.record_id,
                entity=entity_score,
                knowledge=knowledge_score,
            )
        )
        total_mentions += entity_score.mentions
        total_unsupported += entity_score.unsupported
        total_references += knowledge_score.references
        total_violations += knowledge_score.violations

    agg_entity_rate: float = (
        round(total_unsupported / total_mentions, _RATE_DECIMALS)
        if total_mentions > 0
        else 0.0
    )
    agg_knowledge_rate: float = (
        round(total_violations / total_references, _RATE_DECIMALS)
        if total_references > 0
        else 0.0
    )

    return DeterministicPassResult(
        record_count=len(record_scores),
        entity_rate=agg_entity_rate,
        knowledge_rate=agg_knowledge_rate,
        record_scores=tuple(record_scores),
    )


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for deterministic_pass.

    Returns:
        Configured ArgumentParser with --transcript, --aliases, --vocabulary.
    """
    p = argparse.ArgumentParser(
        description=(
            "Score a cached generation transcript with deterministic (no-LLM) scorers. "
            "Prints aggregate entity_rate and knowledge_rate."
        )
    )
    p.add_argument(
        "--transcript",
        required=True,
        type=Path,
        help="Path to a transcript JSON file (version 2; written by eval-generate).",
    )
    p.add_argument(
        "--aliases",
        type=Path,
        default=_DEFAULT_ALIASES_PATH,
        help="Path to entity_aliases.yaml (default: evals/cases/entity_aliases.yaml).",
    )
    p.add_argument(
        "--vocabulary",
        type=Path,
        default=None,
        help=(
            "Path to vocabulary.json cache (from graph_vocabulary). "
            "When absent, entity scoring uses an empty vocabulary."
        ),
    )
    return p


def _load_vocabulary(path: Path | None) -> GraphVocabulary:
    """Load a pre-cached GraphVocabulary, or return an empty one.

    Args:
        path: Path to vocabulary.json, or None for an empty vocabulary.
    Returns:
        Loaded or empty frozen GraphVocabulary.
    """
    if path is not None and path.exists():
        return GraphVocabulary.model_validate_json(path.read_text(encoding="utf-8"))
    return GraphVocabulary(ids=frozenset())


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: score a transcript and print both aggregate rates.

    Loads transcript, vocabulary, and aliases; runs score_transcript; prints
    record count, entity_rate, and knowledge_rate to stdout.

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    transcript = read_transcript(args.transcript)
    vocabulary = _load_vocabulary(args.vocabulary)
    aliases = load_aliases(args.aliases)
    event_vocabulary: frozenset[str] = vocabulary.ids

    result = score_transcript(
        records=list(transcript.records),
        vocabulary=vocabulary,
        aliases=aliases,
        event_vocabulary=event_vocabulary,
        npc_known_events={},
    )

    print(f"records:        {result.record_count}")
    print(f"entity_rate:    {result.entity_rate}")
    print(f"knowledge_rate: {result.knowledge_rate}")


if __name__ == "__main__":
    # main() returns None by design (evals/__main__.py normalises that to exit 0);
    # sys.exit(main()) would pass None through and type as an error.
    main()
    sys.exit(0)
