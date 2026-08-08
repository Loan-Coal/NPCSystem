"""
Module: test_label_import
Layer: test (unit)
Purpose: Unit tests for label_import.py — validating import of Claude-CLI labelling sessions.
         Covers UnknownRecordIdError, ContaminatedRowError, 5-row happy path,
         and byte-identical round-trip through write_calibration_labels.
Dependencies: pathlib, pytest, pydantic, calibration_records, label_import (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from calibration_records import CalibrationLabel, read_calibration_labels, write_calibration_labels
from label_import import (
    ContaminatedRowError,
    MissingVerdictError,
    UnknownRecordIdError,
    import_labels,
)
from record_identity import composite_item_id

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PRE_LABELLER = "claude-opus-5"

# Both indexes are keyed by the repetition-qualified item id, which is what
# _build_transcript_index / _build_judged_index now emit. Raw label rows below
# stay bare on purpose: import_labels must normalise a bare id to repetition 0.
_TRANSCRIPT_INDEX: dict[str, str] = {
    composite_item_id(record_id, 0): text
    for record_id, text in {
        "case_001:tone_judge:0": "Sure, I can help you with that.",
        "case_002:affirms_judge:0": "Yes, the northern war has begun.",
        "case_003:refusal_judge:0": "I cannot assist with that request.",
        "case_004:tone_judge:1": "Happy to assist you, traveller.",
        "case_005:affirms_judge:1": "Indeed, the guard captain told me so.",
    }.items()
}

_JUDGED_INDEX: dict[str, bool] = {
    composite_item_id(record_id, 0): verdict
    for record_id, verdict in {
        "case_001:tone_judge:0": True,
        "case_002:affirms_judge:0": False,
        "case_003:refusal_judge:0": True,
        "case_004:tone_judge:1": True,
        "case_005:affirms_judge:1": False,
    }.items()
}

_RAW_ROWS: list[dict[str, Any]] = [
    {"record_id": "case_001:tone_judge:0", "scorer": "tone_judge", "pre_label": True, "notes": ""},
    {"record_id": "case_002:affirms_judge:0", "scorer": "affirms_judge", "pre_label": False, "notes": "wrong"},
    {"record_id": "case_003:refusal_judge:0", "scorer": "refusal_judge", "pre_label": True, "notes": ""},
    {"record_id": "case_004:tone_judge:1", "scorer": "tone_judge", "pre_label": True, "notes": ""},
    {"record_id": "case_005:affirms_judge:1", "scorer": "affirms_judge", "pre_label": False, "notes": ""},
]


# ---------------------------------------------------------------------------
# Tests — error cases
# ---------------------------------------------------------------------------


def test_unknown_record_id_is_rejected_not_dropped() -> None:
    """A raw row naming a record_id absent from the transcript raises UnknownRecordIdError."""
    bad_row = [{"record_id": "DOES_NOT_EXIST:tone_judge:0", "scorer": "tone_judge", "pre_label": True, "notes": ""}]
    with pytest.raises(UnknownRecordIdError) as exc_info:
        import_labels(bad_row, _TRANSCRIPT_INDEX, _JUDGED_INDEX, _PRE_LABELLER)
    assert "DOES_NOT_EXIST:tone_judge:0" in str(exc_info.value)


def test_contaminated_row_with_output_text_raises() -> None:
    """A raw row carrying output_text is rejected as contaminated."""
    row = [
        {
            "record_id": "case_001:tone_judge:0",
            "scorer": "tone_judge",
            "pre_label": True,
            "notes": "",
            "output_text": "injected text",
        }
    ]
    with pytest.raises(ContaminatedRowError) as exc_info:
        import_labels(row, _TRANSCRIPT_INDEX, _JUDGED_INDEX, _PRE_LABELLER)
    assert "output_text" in str(exc_info.value)


def test_contaminated_row_with_scorer_verdict_raises() -> None:
    """A raw row carrying scorer_verdict is rejected as contaminated."""
    row = [
        {
            "record_id": "case_001:tone_judge:0",
            "scorer": "tone_judge",
            "pre_label": True,
            "notes": "",
            "scorer_verdict": True,
        }
    ]
    with pytest.raises(ContaminatedRowError) as exc_info:
        import_labels(row, _TRANSCRIPT_INDEX, _JUDGED_INDEX, _PRE_LABELLER)
    assert "scorer_verdict" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Tests — happy path
# ---------------------------------------------------------------------------


def test_five_raw_rows_produce_five_labels_with_null_verdict() -> None:
    """5 raw rows produce 5 CalibrationLabel rows, all with human_verdict=None."""
    labels = import_labels(_RAW_ROWS, _TRANSCRIPT_INDEX, _JUDGED_INDEX, _PRE_LABELLER)
    assert len(labels) == 5
    for label in labels:
        assert isinstance(label, CalibrationLabel)
        assert label.human_verdict is None
        assert label.adjudicated_at is None
        assert label.pre_labeller_model == _PRE_LABELLER


def test_import_joins_output_text_from_transcript() -> None:
    """Imported labels carry output_text from the transcript index, not from raw rows."""
    labels = import_labels(_RAW_ROWS, _TRANSCRIPT_INDEX, _JUDGED_INDEX, _PRE_LABELLER)
    by_id = {lbl.record_id: lbl for lbl in labels}
    assert by_id["case_001:tone_judge:0"].output_text == "Sure, I can help you with that."
    assert by_id["case_003:refusal_judge:0"].output_text == "I cannot assist with that request."


def test_import_joins_scorer_verdict_from_judged_index() -> None:
    """Imported labels carry scorer_verdict from the judged index."""
    labels = import_labels(_RAW_ROWS, _TRANSCRIPT_INDEX, _JUDGED_INDEX, _PRE_LABELLER)
    by_id = {lbl.record_id: lbl for lbl in labels}
    assert by_id["case_001:tone_judge:0"].scorer_verdict is True
    assert by_id["case_002:affirms_judge:0"].scorer_verdict is False


def test_import_preserves_pre_label() -> None:
    """Imported labels carry pre_label from the raw row."""
    labels = import_labels(_RAW_ROWS, _TRANSCRIPT_INDEX, _JUDGED_INDEX, _PRE_LABELLER)
    by_id = {lbl.record_id: lbl for lbl in labels}
    assert by_id["case_002:affirms_judge:0"].pre_label is False
    assert by_id["case_002:affirms_judge:0"].notes == "wrong"


def test_round_trip_is_byte_identical(tmp_path: Path) -> None:
    """Round-tripping imported labels through write_calibration_labels is byte-identical."""
    labels = import_labels(_RAW_ROWS, _TRANSCRIPT_INDEX, _JUDGED_INDEX, _PRE_LABELLER)
    out = tmp_path / "labels.jsonl"
    write_calibration_labels(out, labels)
    loaded = read_calibration_labels(out)
    assert loaded == labels


# ---------------------------------------------------------------------------
# Repetition identity (regression: k-repeat runs collapsing to one record)
# ---------------------------------------------------------------------------


def test_repetitions_join_to_their_own_output_and_verdict() -> None:
    """Each repetition of a case keeps its own output_text and scorer_verdict.

    Regression test: GenerationRecord.record_id omits `repetition`, so a k=3 run
    emits three records sharing one record_id with different npc_response text.
    While the indexes were keyed on the bare record_id, only the last repetition
    survived and every label was joined to it — silently pairing a label made
    against one response with a different response's verdict.
    """
    base = "case_001:tone_judge:0"
    transcript = {
        composite_item_id(base, 0): "First reply.",
        composite_item_id(base, 1): "Second reply.",
        composite_item_id(base, 2): "Third reply.",
    }
    judged = {
        composite_item_id(base, 0): True,
        composite_item_id(base, 1): False,
        composite_item_id(base, 2): True,
    }
    raw = [
        {"record_id": composite_item_id(base, i), "scorer": "tone_judge",
         "pre_label": True, "notes": ""}
        for i in range(3)
    ]

    labels = import_labels(raw, transcript, judged, _PRE_LABELLER)

    assert len(labels) == 3
    assert [lbl.output_text for lbl in labels] == ["First reply.", "Second reply.", "Third reply."]
    assert [lbl.scorer_verdict for lbl in labels] == [True, False, True]
    assert len({lbl.record_id for lbl in labels}) == 3


def test_missing_scorer_verdict_is_rejected_not_defaulted() -> None:
    """A record with no verdict in any judged file raises rather than importing False.

    Deterministic scorers are absent from the LLM judge's judged.jsonl; importing
    them with a default False would fabricate calibration data points.
    """
    raw = [{"record_id": "case_001:tone_judge:0", "scorer": "tone_judge",
            "pre_label": True, "notes": ""}]
    with pytest.raises(MissingVerdictError):
        import_labels(raw, _TRANSCRIPT_INDEX, {}, _PRE_LABELLER)
