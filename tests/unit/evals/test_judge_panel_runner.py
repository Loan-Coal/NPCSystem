"""
Module: test_judge_panel_runner
Layer: test (unit)
Purpose: RED anchor + behaviour tests for evals/judge_panel_runner.py — the
         live wiring of the judge panel (EVAL-P21.1/P21.2) into the
         generate->judge pipeline. The critical correctness property under
         test is polarity: judge_panel.consensus_verdict expects "did this
         judge vote fail" booleans, but PanelVerdict.score is the raw YES/NO
         judge answer — feeding raw scores straight into consensus_verdict
         would silently invert the result for pass_on_yes records (tone_judge,
         affirms_judge) while happening to read correctly for pass_on_no
         records (refusal_judge), because only the latter's "YES=fail"
         reading matches consensus_verdict's literal True=fail assumption.
Dependencies: pytest; eval_records, matchers, judge_panel, judge_panel_runner (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

from eval_records import GenerationRecord, write_generation_dir
from judge_panel import PanelVerdict
from judge_panel_runner import (
    _panel_fail_votes,
    _score_record_panel,
    judge_transcript_panel,
    panel_agreement_from_verdicts,
    write_panel_judged_jsonl,
)
from matchers import JudgeResult

_MODELS = ("mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b")


def _verdicts(record_id: str, scores: list[bool | None]) -> list[PanelVerdict]:
    return [
        PanelVerdict(record_id=record_id, judge_model=m, score=s, error="" if s is not None else "infra_failure")
        for m, s in zip(_MODELS, scores)
    ]


def _record(
    record_id: str,
    *,
    polarity: str,
    judge_kind: str | None = "tone_judge",
    npc_response: str = "a response",
) -> GenerationRecord:
    return GenerationRecord(
        record_id=record_id,
        source="runner",
        npc_id="mira_innkeeper",
        player_id="player_1",
        player_message="where are the troops",
        npc_response=npc_response,
        criteria="be gruff",
        judge_kind=judge_kind,  # type: ignore[arg-type]
        expected_polarity=polarity,  # type: ignore[arg-type]
    )


def _stub_judge_fn(votes_by_model: dict[str, bool | None]):
    def judge_fn(model: str, criteria: str, content: str) -> JudgeResult:
        score = votes_by_model[model]
        return JudgeResult(score=score, error="" if score is not None else "infra_failure")
    return judge_fn


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_panel_fail_votes_respects_pass_on_yes_polarity() -> None:
    """YES (score=True) on a pass_on_yes record means the judge said PASS,
    not fail — feeding raw scores unflipped would report this as a fail vote.
    """
    verdicts = _verdicts("case_x:tone_judge:0", [True, True, True])
    votes = _panel_fail_votes(verdicts, "pass_on_yes")
    assert votes == [False, False, False]  # all three judges voted PASS


def test_panel_fail_votes_respects_pass_on_no_polarity() -> None:
    """YES (score=True) on a pass_on_no record means the judge said FAIL —
    the opposite reading from the pass_on_yes case above."""
    verdicts = _verdicts("case_x:refusal_judge:0", [True, True, True])
    votes = _panel_fail_votes(verdicts, "pass_on_no")
    assert votes == [True, True, True]  # all three judges voted FAIL


def test_panel_fail_votes_preserves_none_as_inconclusive() -> None:
    """An infra failure (score=None) must stay None, never coerced to a vote."""
    verdicts = _verdicts("case_x:tone_judge:0", [True, None, False])
    votes = _panel_fail_votes(verdicts, "pass_on_yes")
    assert votes == [False, None, True]


# ---------------------------------------------------------------------------
# Consensus behaviour
# ---------------------------------------------------------------------------


def test_two_of_three_fail_votes_confirms_failure() -> None:
    """>=2-of-3 judges voting fail (under the record's own polarity) flips
    the consensus JudgedRecord to passed=False."""
    record = _record("case_x:refusal_judge:0", polarity="pass_on_no")
    judge_fn = _stub_judge_fn({
        "mixtral:8x7b": True, "qwen2.5:14b": True, "llama3.1:8b": False,
    })
    judged, verdicts = _score_record_panel(record, _MODELS, judge_fn)
    assert judged.passed is False
    assert len(verdicts) == 3


def test_single_dissenting_judge_does_not_confirm_failure() -> None:
    """The audited case_neg_injection_001 false positive: one judge dissents,
    the record must still pass — a single vote cannot outvote the other two."""
    record = _record("case_x:refusal_judge:0", polarity="pass_on_no")
    judge_fn = _stub_judge_fn({
        "mixtral:8x7b": True, "qwen2.5:14b": False, "llama3.1:8b": False,
    })
    judged, _ = _score_record_panel(record, _MODELS, judge_fn)
    assert judged.passed is True


def test_all_infra_failures_yield_none_score_not_a_silent_pass() -> None:
    """Every judge erroring must surface as inconclusive (score=None), never
    a silent pass — DEC-184's own stated requirement."""
    record = _record("case_x:tone_judge:0", polarity="pass_on_yes")
    judge_fn = _stub_judge_fn({m: None for m in _MODELS})
    judged, _ = _score_record_panel(record, _MODELS, judge_fn)
    assert judged.score is None
    assert judged.passed is True  # no confirmed failure votes either


# ---------------------------------------------------------------------------
# End-to-end: transcript -> judged records + persisted verdicts
# ---------------------------------------------------------------------------


def test_judge_transcript_panel_scores_every_judge_kind_record(tmp_path: Path) -> None:
    """Records with judge_kind=None (deterministic) are skipped, matching
    judge_runner.judge_transcript's own contract."""
    records = [
        _record("case_a:tone_judge:0", polarity="pass_on_yes"),
        _record("case_b:schema:0", polarity="pass_on_yes", judge_kind=None),
    ]
    gen_dir = tmp_path / "gen"
    write_generation_dir(gen_dir, records, gen_id="t", k=1)
    judge_fn = _stub_judge_fn({m: True for m in _MODELS})
    judged_records, all_verdicts = judge_transcript_panel(
        gen_dir / "outputs.jsonl", _MODELS, judge_fn=judge_fn
    )
    assert len(judged_records) == 1
    assert judged_records[0].record_id == "case_a:tone_judge:0"
    assert len(all_verdicts) == 3  # one record x 3 seats


def test_write_panel_judged_jsonl_emits_one_row_per_judge_per_record(tmp_path: Path) -> None:
    """A record judged by 3 models yields 3 rows — DEC-184's validation clause."""
    verdicts = _verdicts("case_x:tone_judge:0", [True, False, None])
    out = tmp_path / "judged.jsonl"
    write_panel_judged_jsonl(verdicts, out)
    lines = [l for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3
    import json
    rows = [json.loads(l) for l in lines]
    assert {r["judge_model"] for r in rows} == set(_MODELS)
    assert any(r["inconclusive"] for r in rows)


def test_panel_agreement_from_verdicts_groups_by_record() -> None:
    """Agreement is computed per-record then aggregated pairwise — two records
    with different vote patterns must both contribute pairs."""
    all_verdicts = _verdicts("case_a:tone_judge:0", [True, True, True]) + _verdicts(
        "case_b:tone_judge:0", [True, False, True]
    )
    result = panel_agreement_from_verdicts(all_verdicts)
    assert result.total_pairs == 6  # 3 pairs per record x 2 records
    assert result.agreeing_pairs == 4  # case_a: 3/3 agree, case_b: 1/3 agree
