"""
Module: test_judged_persistence
Layer: test (unit)
Purpose: Tests for evals/judged_persistence.py — the single module that owns the
         judged.jsonl row schema for BOTH the single-judge and the panel path.
         RED anchors for the two defects the 2026-08-17 overnight panel run
         exposed (ISSUE-179 polarity inversion, ISSUE-180 dropped repetition)
         plus the schema-parity guard that prevents the divergence recurring.
Dependencies: pytest, eval_records, judge_panel, judged_persistence (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

import json

from eval_records import GenerationRecord, JudgedRecord
from judge_panel import PanelScoredRecord, PanelVerdict
from judged_persistence import (
    consensus_rows,
    judged_rows,
    seat_rows,
    write_consensus_jsonl,
    write_seat_votes_jsonl,
)

_PANEL = ("mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b")


def _record(
    *,
    record_id: str = "case_x:affirms_judge:5",
    judge_kind: str = "affirms_judge",
    polarity: str = "pass_on_no",
    repetition: int = 0,
) -> GenerationRecord:
    """Build a minimal GenerationRecord for row-shape assertions."""
    return GenerationRecord(
        record_id=record_id,
        source="anti_hallucination",
        npc_id="captain_sorn",
        player_id="player_1",
        player_message="did the war end?",
        npc_response="I'm just a humble captain of the guard.",
        criteria="Does the NPC affirm that the war has ended?",
        judge_kind=judge_kind,
        expected_polarity=polarity,
        repetition=repetition,
    )


def _scored(record: GenerationRecord, scores: dict[str, bool | None]) -> PanelScoredRecord:
    """Pair a record with one PanelVerdict per seat."""
    return PanelScoredRecord(
        record=record,
        verdicts=tuple(
            PanelVerdict(
                record_id=record.record_id,
                judge_model=model,
                score=score,
                error="" if score in (True, None) else "did not affirm",
            )
            for model, score in scores.items()
        ),
    )


# ---------------------------------------------------------------------------
# RED anchor — ISSUE-179: seat rows must apply expected_polarity
# ---------------------------------------------------------------------------


def test_seat_rows_apply_expected_polarity() -> None:
    """pass_on_no + score=False means the NPC did NOT affirm the lie → passed=True.

    The 2026-08-17 panel run persisted `passed: bool(score)`, inverting this for
    every affirms_judge row (135 of 345 per judge).
    """
    scored = _scored(_record(polarity="pass_on_no"), {m: False for m in _PANEL})
    rows = seat_rows([scored])

    assert len(rows) == 3
    assert all(r["score"] is False for r in rows)
    assert all(r["passed"] is True for r in rows), "pass_on_no: a NO verdict is a PASS"


def test_seat_rows_polarity_pass_on_yes_is_unchanged() -> None:
    """pass_on_yes + score=True → passed=True (the polarity that was accidentally correct)."""
    record = _record(record_id="case_x:tone_judge:5", judge_kind="tone_judge", polarity="pass_on_yes")
    rows = seat_rows([_scored(record, {m: True for m in _PANEL})])
    assert all(r["passed"] is True for r in rows)


def test_seat_rows_inconclusive_is_never_a_silent_pass() -> None:
    """score=None yields passed=False and inconclusive=True under BOTH polarities."""
    for polarity in ("pass_on_yes", "pass_on_no"):
        rows = seat_rows([_scored(_record(polarity=polarity), {m: None for m in _PANEL})])
        assert all(r["passed"] is False for r in rows), polarity
        assert all(r["inconclusive"] is True for r in rows), polarity


# ---------------------------------------------------------------------------
# RED anchor — ISSUE-180: seat rows must carry repetition
# ---------------------------------------------------------------------------


def test_seat_rows_carry_repetition() -> None:
    """Each seat row records which of the k repeats it judged.

    Without this, transcript_index.build_judged_index defaults every row to
    repetition 0, collapsing all k repeats onto one key (last write wins).
    """
    scored = [
        _scored(_record(repetition=rep), {m: True for m in _PANEL})
        for rep in (0, 1, 2)
    ]
    rows = seat_rows(scored)

    keys = {(r["record_id"], r["repetition"], r["judge_model"]) for r in rows}
    assert len(keys) == 9, "3 repeats x 3 seats must be 9 distinct addressable rows"
    assert {r["repetition"] for r in rows} == {0, 1, 2}


# ---------------------------------------------------------------------------
# The schema-parity guard — root cause of the whole defect class
# ---------------------------------------------------------------------------


def test_seat_rows_are_a_superset_of_single_judge_rows() -> None:
    """Panel rows must carry every field a single-judge row carries.

    The 2026-08-17 divergence (panel emitted 6 fields, single-judge emitted 8)
    is what dropped case_id/judge_kind/repetition. This test fails if the two
    schemas drift apart again.
    """
    record = _record()
    judged = JudgedRecord(**record.model_dump(), passed=True, score=False, reasoning="")

    single = judged_rows([judged], judge_model="mixtral:8x7b")[0]
    seat = seat_rows([_scored(record, {m: False for m in _PANEL})])[0]

    missing = set(single) - set(seat)
    assert not missing, f"panel seat rows dropped single-judge fields: {sorted(missing)}"
    assert seat["case_id"] == "case_x"
    assert seat["judge_kind"] == "affirms_judge"


def test_consensus_rows_are_one_per_record_and_match_single_judge_schema() -> None:
    """Consensus rows keep the historical one-row-per-record shape readers expect."""
    record = _record()
    judged = JudgedRecord(**record.model_dump(), passed=True, score=False, reasoning="")

    rows = consensus_rows([judged], panel_size=3)
    reference = judged_rows([judged], judge_model="mixtral:8x7b")[0]

    assert len(rows) == 1
    assert set(rows[0]) == set(reference)
    assert rows[0]["judge_model"] == "panel:3"
    assert rows[0]["passed"] is True


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


def test_writers_emit_two_files_with_the_expected_row_counts(tmp_path) -> None:
    """Consensus file gets 1 row per record; votes file gets 1 row per seat per record."""
    records = [_record(repetition=rep) for rep in (0, 1, 2)]
    scored = [_scored(r, {m: False for m in _PANEL}) for r in records]
    judged = [
        JudgedRecord(**r.model_dump(), passed=True, score=False, reasoning="")
        for r in records
    ]

    consensus_path = tmp_path / "judged.jsonl"
    votes_path = tmp_path / "judged_panel_votes.jsonl"
    write_consensus_jsonl(judged, consensus_path, panel_size=3)
    write_seat_votes_jsonl(scored, votes_path)

    consensus = [json.loads(x) for x in consensus_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    votes = [json.loads(x) for x in votes_path.read_text(encoding="utf-8").splitlines() if x.strip()]

    assert len(consensus) == 3
    assert len(votes) == 9
    assert {v["judge_model"] for v in votes} == set(_PANEL)
