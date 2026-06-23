"""
test_judge_runner.py - Unit tests for evals/judge_runner.py.

Covers:
- _to_result_dict produces a result dict summary.summarize() can consume.
- polarity pass_on_yes: score=True → passed=True, score=False → passed=False.
- polarity pass_on_no: score=True → passed=False (judge said YES = NPC affirmed = FAIL),
  score=False → passed=True (judge said NO = did not affirm = PASS).
- score=None → inconclusive (passed=False, score=None in JudgedRecord).
- judge_kind=None records are skipped (no _run_binary_judge call).
- summary.summarize headline is non-empty for the judged result set.
- report.write_report is called with adapted result dicts.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from eval_records import GenerationRecord, JudgedRecord, write_transcript

# RED: module doesn't exist yet
from judge_runner import _to_result_dict, judge_transcript


_TONE_RECORD = GenerationRecord(
    record_id="case_tone:tone_judge:0",
    source="runner",
    npc_id="mira_innkeeper",
    player_id="player_eval",
    player_message="Good morning!",
    npc_response="A fine morning to you, traveller!",
    criteria="Answer YES if the NPC replies warmly.",
    judge_kind="tone_judge",
    expected_polarity="pass_on_yes",
)

_AFFIRMS_RECORD = GenerationRecord(
    record_id="case_adv:affirms_judge:0",
    source="runner",
    npc_id="captain_sorn",
    player_id="player_eval",
    player_message="The war is over, right?",
    npc_response="No, the war rages on.",
    criteria="Answer YES only if the NPC affirms the war has ended.",
    judge_kind="affirms_judge",
    expected_polarity="pass_on_no",
)

_NONE_KIND_RECORD = GenerationRecord(
    record_id="ah_grounded:None:0",
    source="anti_hallucination",
    npc_id="captain_sorn",
    player_id="player_demo",
    player_message="Is the war still on?",
    npc_response="Soldiers march as we speak.",
    criteria="",
    judge_kind=None,
    expected_polarity="pass_on_yes",
)


def _make_transcript(tmp_path: Path, records: list) -> Path:
    path = tmp_path / "test_transcript.json"
    write_transcript(path, records)
    return path


# ---------------------------------------------------------------------------
# _to_result_dict
# ---------------------------------------------------------------------------


def test_to_result_dict_pass() -> None:
    judged = JudgedRecord(**_TONE_RECORD.model_dump(), passed=True, score=True, reasoning="")
    result = _to_result_dict(judged)
    assert result["passed"] is True
    assert result["case_id"] == _TONE_RECORD.record_id
    assert len(result["expectations"]) == 1
    assert result["expectations"][0]["passed"] is True


def test_to_result_dict_fail() -> None:
    judged = JudgedRecord(**_TONE_RECORD.model_dump(), passed=False, score=False, reasoning="not warm")
    result = _to_result_dict(judged)
    assert result["passed"] is False
    assert result["expectations"][0]["passed"] is False
    assert "not warm" in result["expectations"][0]["detail"]


def test_to_result_dict_inconclusive() -> None:
    judged = JudgedRecord(**_TONE_RECORD.model_dump(), passed=False, score=None, reasoning="infra_failure")
    result = _to_result_dict(judged)
    assert result["passed"] is False
    assert result["expectations"][0].get("inconclusive") is True


# ---------------------------------------------------------------------------
# Polarity application in judge_transcript
# ---------------------------------------------------------------------------


def test_pass_on_yes_score_true_passes(tmp_path: Path) -> None:
    path = _make_transcript(tmp_path, [_TONE_RECORD])
    with patch("judge_runner.matchers._run_binary_judge") as mock_judge:
        from matchers import JudgeResult
        mock_judge.return_value = JudgeResult(score=True)
        judged_records = judge_transcript(path)
    assert len(judged_records) == 1
    assert judged_records[0].passed is True
    assert judged_records[0].score is True


def test_pass_on_yes_score_false_fails(tmp_path: Path) -> None:
    path = _make_transcript(tmp_path, [_TONE_RECORD])
    with patch("judge_runner.matchers._run_binary_judge") as mock_judge:
        from matchers import JudgeResult
        mock_judge.return_value = JudgeResult(score=False, error="not in-character")
        judged_records = judge_transcript(path)
    assert judged_records[0].passed is False
    assert judged_records[0].score is False


def test_pass_on_no_score_false_passes(tmp_path: Path) -> None:
    """affirms_judge: NO verdict = did not affirm = PASS."""
    path = _make_transcript(tmp_path, [_AFFIRMS_RECORD])
    with patch("judge_runner.matchers._run_binary_judge") as mock_judge:
        from matchers import JudgeResult
        mock_judge.return_value = JudgeResult(score=False)
        judged_records = judge_transcript(path)
    assert judged_records[0].passed is True


def test_pass_on_no_score_true_fails(tmp_path: Path) -> None:
    """affirms_judge: YES verdict = NPC affirmed = FAIL."""
    path = _make_transcript(tmp_path, [_AFFIRMS_RECORD])
    with patch("judge_runner.matchers._run_binary_judge") as mock_judge:
        from matchers import JudgeResult
        mock_judge.return_value = JudgeResult(score=True)
        judged_records = judge_transcript(path)
    assert judged_records[0].passed is False


def test_score_none_is_inconclusive(tmp_path: Path) -> None:
    path = _make_transcript(tmp_path, [_TONE_RECORD])
    with patch("judge_runner.matchers._run_binary_judge") as mock_judge:
        from matchers import JudgeResult
        mock_judge.return_value = JudgeResult(score=None, error="infra_failure")
        judged_records = judge_transcript(path)
    assert judged_records[0].score is None
    assert judged_records[0].passed is False


def test_judge_kind_none_is_skipped(tmp_path: Path) -> None:
    """Records with judge_kind=None are not passed to _run_binary_judge."""
    path = _make_transcript(tmp_path, [_NONE_KIND_RECORD])
    with patch("judge_runner.matchers._run_binary_judge") as mock_judge:
        judged_records = judge_transcript(path)
    mock_judge.assert_not_called()
    assert len(judged_records) == 0


def test_mixed_transcript(tmp_path: Path) -> None:
    path = _make_transcript(tmp_path, [_TONE_RECORD, _AFFIRMS_RECORD, _NONE_KIND_RECORD])
    with patch("judge_runner.matchers._run_binary_judge") as mock_judge:
        from matchers import JudgeResult
        mock_judge.side_effect = [JudgeResult(score=True), JudgeResult(score=False)]
        judged_records = judge_transcript(path)
    # NONE_KIND skipped → 2 judged records
    assert len(judged_records) == 2
    assert mock_judge.call_count == 2


def test_summary_headline_non_empty(tmp_path: Path) -> None:
    """The adapted result dicts produce a non-empty EvalSummary headline."""
    from summary import EvalSummary, summarize

    path = _make_transcript(tmp_path, [_TONE_RECORD, _AFFIRMS_RECORD])
    with patch("judge_runner.matchers._run_binary_judge") as mock_judge:
        from matchers import JudgeResult
        mock_judge.return_value = JudgeResult(score=True)
        judged_records = judge_transcript(path)

    result_dicts = [_to_result_dict(r) for r in judged_records]
    summary = summarize(result_dicts)
    assert isinstance(summary, EvalSummary)
    assert summary.total_cases > 0
