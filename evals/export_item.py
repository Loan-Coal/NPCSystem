"""
Module: export_item
Layer: evals (eval harness — not part of src/)
Purpose: ExportItem model and the GenerationRecord → ExportItem derivation logic
         (criteria rendering, observed-field extraction, scorer resolution).
         Split out of label_export.py so the derivation can be reused by
         transcript_index.py (label_import's join source) without a circular
         import between label_export and label_import.
Dependencies: pydantic, criteria_rendering, eval_records
Used by: label_export (batch construction), transcript_index (label_import's
         join step, EVAL-P5.6 adjudication fix)
"""

from __future__ import annotations

from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict

from criteria_rendering import observed_fields, render_criteria
from eval_records import GenerationRecord
from record_identity import composite_item_id

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Grounded AH records store their parameters directly rather than under
# metadata["expectation"] (see deterministic_records.build_ah_grounded_record).
_GROUNDED_KIND: str = "anti_hallucination_grounded"
_GROUNDED_PARAM_KEY: str = "expected_fact_substrings"

# Scorer kinds whose export items include a vocabulary block so labellers can
# verify entity/event IDs mentioned in output_text against the graph.
GRAPH_SCORER_KINDS: frozenset[str] = frozenset({"entity_scorer", "knowledge_scorer"})


# ---------------------------------------------------------------------------
# Export item model
# ---------------------------------------------------------------------------


class ExportItem(BaseModel):
    """One item in an export batch, ready for the LABEL_PROMPT.md labelling pass.

    Fields deliberately exclude scorer_verdict, judge verdicts, and metadata
    that would reveal the answer the labeller is measuring.

    Attributes:
        record_id: Repetition-qualified identifier ('<case>:<kind>:<index>#r<n>').
                   Unique per labelled output, unlike the transcript's bare
                   record_id which repeats k times in a k-repeat run.
        scorer: Which scorer is being calibrated (e.g. 'tone_judge').
        npc_id: Character that produced the output.
        player_message: The player's dialogue turn that prompted the response.
        criteria: What the scorer requires. Verbatim judge criteria for LLM-judge
                  records; rendered from the matcher's expectation dict for
                  deterministic records (never empty — see criteria_rendering).
        output_text: The NPC response text to be labelled.
        observed: Response fields the matcher inspects beyond output_text
                  (facial_expression.type, relation_deltas.trust, …). Empty for
                  text-only scorers; those are fully judgeable from output_text.
        vocabulary: Graph node-ID snapshot for graph scorer records;
                    None for all other scorer kinds.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    scorer: str
    npc_id: str
    player_message: str
    criteria: str
    output_text: str
    observed: dict[str, Any] = {}
    vocabulary: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _scorer_for_record(record: GenerationRecord) -> str:
    """Derive the calibration scorer name from a GenerationRecord.

    Args:
        record: A GenerationRecord from the generation transcript.
    Returns:
        The judge_kind string if the record is LLM-judged, otherwise
        the matcher_kind string, otherwise 'unknown'.
    """
    if record.judge_kind is not None:
        return str(record.judge_kind)
    if record.matcher_kind is not None:
        return str(record.matcher_kind)
    return "unknown"


def _expectation_for(record: GenerationRecord) -> dict[str, Any]:
    """Recover a deterministic record's matcher parameters from its metadata.

    Grounded AH records store expected_fact_substrings at the top level of
    metadata; every other deterministic kind nests its raw expectation dict
    under metadata["expectation"].
    """
    if record.matcher_kind == _GROUNDED_KIND:
        return {_GROUNDED_PARAM_KEY: record.metadata.get(_GROUNDED_PARAM_KEY, [])}
    return record.metadata.get("expectation", {}) or {}


def build_export_item(
    record: GenerationRecord,
    vocabulary: dict[str, Any] | None = None,
) -> ExportItem:
    """Build one ExportItem from a GenerationRecord.

    LLM-judge records carry their criteria verbatim. Deterministic records carry
    criteria="" on the record itself (the field is reserved for judge prompts),
    so their criteria is rendered from metadata["expectation"] and the response
    fields the matcher inspects are surfaced in `observed` — without both, the
    item is unlabelable.

    scorer_verdict and judge verdicts are never included.

    Args:
        record: Source GenerationRecord.
        vocabulary: Graph vocabulary dict to include for graph scorer records;
                    ignored (left None) for non-graph scorer records.
    Returns:
        An ExportItem suitable for JSON serialisation.
    Raises:
        UnknownMatcherKindError: If a deterministic record's matcher kind has no
            rendering rule — a silent blank criteria would make it unlabelable.
    """
    scorer = _scorer_for_record(record)
    criteria = record.criteria
    observed: dict[str, Any] = {}

    if record.judge_kind is None and record.matcher_kind is not None:
        expectation = _expectation_for(record)
        response = record.metadata.get("response", {}) or {}
        criteria = render_criteria(scorer, expectation)
        observed = observed_fields(scorer, expectation, response)

    return ExportItem(
        record_id=composite_item_id(record.record_id, record.repetition),
        scorer=scorer,
        npc_id=record.npc_id,
        player_message=record.player_message,
        criteria=criteria,
        output_text=record.npc_response,
        observed=observed,
        vocabulary=vocabulary if scorer in GRAPH_SCORER_KINDS else None,
    )


def build_export_items(
    records: Sequence[GenerationRecord],
    vocabulary: dict[str, Any] | None = None,
) -> list[ExportItem]:
    """Build export items from a sequence of GenerationRecords.

    Args:
        records: GenerationRecords from the generation transcript.
        vocabulary: Graph vocabulary dict; included only for graph scorer records.
    Returns:
        List of ExportItems in the same order as records.
    """
    return [build_export_item(record, vocabulary) for record in records]
