"""
Module: test_calibration_records
Layer: test (unit)
Purpose: Unit tests for calibration_records.py — CalibrationLabel model and JSONL
         round-trip persistence for the EVAL-P5 calibration artifact.
         Covers the scorer_verdict field added in EVAL-P5.5.
Dependencies: json, pathlib, pytest, pydantic, calibration_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from calibration_records import (
    CalibrationLabel,
    read_calibration_labels,
    write_calibration_labels,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_UNADJUDICATED = CalibrationLabel(
    record_id="case_001:tone_judge:0",
    scorer="tone_judge",
    output_text="Sure, I can help you with that.",
    scorer_verdict=True,
    pre_label=True,
    pre_labeller_model="claude-opus-5",
    human_verdict=None,
    adjudicated_at=None,
    notes="",
)

_ADJUDICATED = CalibrationLabel(
    record_id="case_002:refusal_judge:0",
    scorer="refusal_judge",
    output_text="I cannot assist with that request.",
    scorer_verdict=False,
    pre_label=False,
    pre_labeller_model="claude-opus-5",
    human_verdict=True,
    adjudicated_at="2026-08-07T10:00:00+00:00",
    notes="Model was wrong; clearly a refusal.",
)

_THIRD = CalibrationLabel(
    record_id="case_003:affirms_judge:0",
    scorer="affirms_judge",
    output_text="Yes, the northern war has begun.",
    scorer_verdict=True,
    pre_label=True,
    pre_labeller_model="claude-opus-5",
    human_verdict=True,
    adjudicated_at="2026-08-07T10:01:00+00:00",
    notes="",
)


# ---------------------------------------------------------------------------
# Tests — model constraints
# ---------------------------------------------------------------------------


def test_unadjudicated_row_round_trips_with_null_verdict(tmp_path: Path) -> None:
    """Unadjudicated row serialises and deserialises with human_verdict=None intact."""
    out = tmp_path / "labels.jsonl"
    write_calibration_labels(out, [_UNADJUDICATED])
    rows = read_calibration_labels(out)
    assert len(rows) == 1
    assert rows[0] == _UNADJUDICATED
    assert rows[0].human_verdict is None
    assert rows[0].adjudicated_at is None


def test_three_rows_round_trip_byte_identically(tmp_path: Path) -> None:
    """3 rows written then read back are identical to the originals."""
    out = tmp_path / "labels.jsonl"
    originals = [_UNADJUDICATED, _ADJUDICATED, _THIRD]
    write_calibration_labels(out, originals)
    rows = read_calibration_labels(out)
    assert rows == originals


def test_missing_pre_labeller_model_raises_validation_error() -> None:
    """A row missing pre_labeller_model must not be constructible."""
    with pytest.raises(ValidationError):
        CalibrationLabel(
            record_id="x",
            scorer="tone_judge",
            output_text="hello",
            scorer_verdict=True,
            pre_label=True,
            # pre_labeller_model omitted — required field
            human_verdict=None,
            adjudicated_at=None,
            notes="",
        )


def test_missing_scorer_verdict_raises_validation_error() -> None:
    """A row missing scorer_verdict must not be constructible."""
    with pytest.raises(ValidationError):
        CalibrationLabel(
            record_id="x",
            scorer="tone_judge",
            output_text="hello",
            # scorer_verdict omitted — required field
            pre_label=True,
            pre_labeller_model="claude-opus-5",
            human_verdict=None,
            adjudicated_at=None,
            notes="",
        )


def test_output_text_stored_inline(tmp_path: Path) -> None:
    """output_text is stored verbatim in each JSONL line, not as a pointer."""
    out = tmp_path / "labels.jsonl"
    write_calibration_labels(out, [_UNADJUDICATED])
    line = out.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert parsed["output_text"] == _UNADJUDICATED.output_text


def test_label_is_frozen() -> None:
    """CalibrationLabel is immutable — attribute assignment is rejected by Pydantic."""
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises((TypeError, AttributeError, PydanticValidationError)):
        _UNADJUDICATED.human_verdict = True  # type: ignore[misc]


def test_jsonl_one_line_per_row(tmp_path: Path) -> None:
    """JSONL file has exactly as many non-empty lines as rows written."""
    out = tmp_path / "labels.jsonl"
    rows = [_UNADJUDICATED, _ADJUDICATED, _THIRD]
    write_calibration_labels(out, rows)
    lines = [l for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3


# ---------------------------------------------------------------------------
# Tests — criteria / player_message / observed passthrough fields (EVAL adjudication fix)
# ---------------------------------------------------------------------------


def test_new_display_fields_default_when_omitted() -> None:
    """criteria, player_message, and observed default to '' / '' / {} when omitted."""
    row = CalibrationLabel(
        record_id="case_010:in_set:0",
        scorer="in_set",
        output_text="The guard nods grimly.",
        scorer_verdict=True,
        pre_label=True,
        pre_labeller_model="claude-opus-5",
        human_verdict=None,
        adjudicated_at=None,
        notes="",
    )
    assert row.criteria == ""
    assert row.player_message == ""
    assert row.observed == {}


def test_legacy_row_without_new_fields_still_loads(tmp_path: Path) -> None:
    """A JSONL line written before this change (no criteria/player_message/observed) still parses."""
    out = tmp_path / "labels.jsonl"
    legacy_line = json.dumps(
        {
            "record_id": "case_011:tone_judge:0",
            "scorer": "tone_judge",
            "output_text": "Good day, traveller.",
            "scorer_verdict": True,
            "pre_label": True,
            "pre_labeller_model": "claude-opus-5",
            "human_verdict": None,
            "adjudicated_at": None,
            "notes": "",
        }
    )
    out.write_text(legacy_line, encoding="utf-8")
    rows = read_calibration_labels(out)
    assert len(rows) == 1
    assert rows[0].criteria == ""
    assert rows[0].player_message == ""
    assert rows[0].observed == {}


def test_new_fields_round_trip(tmp_path: Path) -> None:
    """criteria, player_message, and observed survive a write/read round trip."""
    row = CalibrationLabel(
        record_id="case_012:in_set:0",
        scorer="in_set",
        output_text="The guard nods grimly.",
        scorer_verdict=True,
        pre_label=True,
        pre_labeller_model="claude-opus-5",
        human_verdict=None,
        adjudicated_at=None,
        notes="",
        criteria="The response field `facial_expression.type` must be one of: 'neutral', 'grim'.",
        player_message="What did you see, guard?",
        observed={"facial_expression.type": "grim"},
    )
    out = tmp_path / "labels.jsonl"
    write_calibration_labels(out, [row])
    loaded = read_calibration_labels(out)
    assert len(loaded) == 1
    assert loaded[0] == row
    assert loaded[0].criteria == row.criteria
    assert loaded[0].player_message == row.player_message
    assert loaded[0].observed == row.observed
