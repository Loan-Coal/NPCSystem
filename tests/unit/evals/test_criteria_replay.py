"""
Module: test_criteria_replay
Layer: test (unit)
Purpose: Unit tests for criteria_replay.py — re-scoring selected calibration
         label rows against a new criteria file without a full judge pass
         (EVAL-P19.0b).
Dependencies: pathlib, pytest, unittest.mock, calibration_records,
              criteria_replay (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from calibration_records import CalibrationLabel
from criteria_replay import load_criteria_text, replay_criteria, select_rows
from matchers import JudgeResult

_LABELLER = "claude-opus-5"


def _label(
    i: int,
    *,
    scorer: str = "refusal_judge",
    scorer_verdict: bool = True,
    human_verdict: bool | None = None,
    output_text: str | None = None,
) -> CalibrationLabel:
    """Build a CalibrationLabel for testing."""
    return CalibrationLabel(
        record_id=f"case_{i:03d}:{scorer}:0",
        scorer=scorer,
        output_text=output_text if output_text is not None else f"Output {i}.",
        scorer_verdict=scorer_verdict,
        pre_label=scorer_verdict,
        pre_labeller_model=_LABELLER,
        human_verdict=human_verdict,
        adjudicated_at="2026-08-07T10:00:00+00:00" if human_verdict is not None else None,
        notes="",
    )


# ---------------------------------------------------------------------------
# select_rows
# ---------------------------------------------------------------------------


def test_select_rows_filters_by_scorer() -> None:
    """Only rows for the requested scorer are selected."""
    rows = [_label(0, scorer="refusal_judge"), _label(1, scorer="tone_judge")]
    selected = select_rows(rows, scorer="refusal_judge")
    assert len(selected) == 1
    assert selected[0].scorer == "refusal_judge"


def test_select_rows_filters_by_record_id_subset() -> None:
    """An explicit record_id subset issues judge calls only for those rows —
    selecting 12 of 393 rows must never touch the other 381."""
    rows = [_label(i) for i in range(20)]
    wanted = {rows[3].record_id, rows[7].record_id}
    selected = select_rows(rows, scorer="refusal_judge", record_ids=wanted)
    assert len(selected) == 2
    assert {r.record_id for r in selected} == wanted


# ---------------------------------------------------------------------------
# load_criteria_text
# ---------------------------------------------------------------------------


def test_load_criteria_text_reads_the_criteria_key(tmp_path: Path) -> None:
    """load_criteria_text reads the 'criteria' key from a judge-criteria YAML."""
    path = tmp_path / "refusal_judge.yaml"
    path.write_text(yaml.safe_dump({"criteria": "Does the response refuse? YES/NO."}), encoding="utf-8")
    assert load_criteria_text(path) == "Does the response refuse? YES/NO."


# ---------------------------------------------------------------------------
# RED anchor — replay_criteria re-scores selected rows against new criteria
# ---------------------------------------------------------------------------


def test_replay_scores_selected_rows_against_new_criteria() -> None:
    """replay_criteria calls the judge once per selected row with the new
    criteria and the row's stored output_text, not the old criteria."""
    rows = [_label(0, output_text="I haven't heard anything.")]
    with patch("criteria_replay.matchers._run_binary_judge") as mock_judge:
        mock_judge.return_value = JudgeResult(score=True)
        result = replay_criteria(rows, "NEW CRITERIA TEXT")

    mock_judge.assert_called_once_with("NEW CRITERIA TEXT", "I haven't heard anything.")
    assert result.n_replayed == 1
    assert result.rows[0].new_verdict is True


def test_a_no_op_replay_reproduces_the_stored_verdict_exactly() -> None:
    """Replaying the unchanged criteria must reproduce scorer_verdict exactly —
    a no-op replay is a no-op."""
    rows = [_label(i, scorer_verdict=(i % 2 == 0)) for i in range(6)]
    verdict_by_content = {row.output_text: row.scorer_verdict for row in rows}
    with patch("criteria_replay.matchers._run_binary_judge") as mock_judge:
        mock_judge.side_effect = lambda criteria, content: JudgeResult(
            score=verdict_by_content[content]
        )
        result = replay_criteria(rows, "UNCHANGED CRITERIA")

    assert result.n_changed == 0
    for old, replayed in zip(rows, result.rows):
        assert replayed.new_verdict == old.scorer_verdict


def test_selecting_12_of_393_rows_issues_exactly_12_judge_calls() -> None:
    """The whole point of this tool: verify a criteria change on a subset
    without spending a 393-row judge pass."""
    rows = [_label(i) for i in range(393)]
    wanted_ids = {r.record_id for r in rows[:12]}
    selected = select_rows(rows, scorer="refusal_judge", record_ids=wanted_ids)

    with patch("criteria_replay.matchers._run_binary_judge") as mock_judge:
        mock_judge.return_value = JudgeResult(score=True)
        replay_criteria(selected, "SOME CRITERIA")

    assert mock_judge.call_count == 12


def test_agreement_counts_only_adjudicated_rows() -> None:
    """n_agree_with_human / n_adjudicated exclude rows with no human_verdict."""
    rows = [
        _label(0, human_verdict=True),
        _label(1, human_verdict=False),
        _label(2, human_verdict=None),
    ]
    with patch("criteria_replay.matchers._run_binary_judge") as mock_judge:
        mock_judge.return_value = JudgeResult(score=True)
        result = replay_criteria(rows, "CRITERIA")

    assert result.n_adjudicated == 2
    assert result.n_agree_with_human == 1  # row 0 agrees (True==True), row 1 does not
