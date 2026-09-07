"""
Module: test_adjudication_yield
Layer: test (unit)
Purpose: Unit tests for adjudication_yield.py — the projection that says whether a
         keep/flip push over the pending pre-labels can lift a scorer to DEC-260's
         adequacy floor, and, when it cannot, why not (DEC-272). The distinction the
         tests pin hardest is "short but reachable by flips" vs "not reachable by
         adjudication at all" — that is the difference between a worthwhile evening
         of adjudication and a wasted one.
Dependencies: pytest, calibration_records (CalibrationLabel), adjudication_yield (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

from adjudication_yield import (
    AdjudicationYield,
    format_yield_table,
    main,
    pending_rows,
    project_adjudication_yield,
    project_all,
)
from calibration_records import CalibrationLabel
from label_adequacy import MIN_MINORITY_LABELS


def _row(
    i: int,
    scorer: str = "tone_judge",
    *,
    human_verdict: bool | None,
    pre_label: bool | None = True,
    case_id: str | None = None,
) -> CalibrationLabel:
    """One CalibrationLabel row; human_verdict None means pending adjudication."""
    return CalibrationLabel(
        record_id=f"{case_id or f'case_{i:03d}'}:{scorer}:0",
        scorer=scorer,
        output_text=f"output {i}",
        scorer_verdict=True,
        pre_label=pre_label,
        pre_labeller_model="claude-opus-5",
        human_verdict=human_verdict,
        adjudicated_at=None if human_verdict is None else "2026-09-01T00:00:00Z",
        notes="",
    )


def _rows(spec: list[tuple[int, bool | None, bool | None]], scorer: str = "tone_judge") -> list[CalibrationLabel]:
    """Build rows from (count, human_verdict, pre_label) triples, each in its own cluster."""
    out: list[CalibrationLabel] = []
    i = 0
    for count, verdict, pre in spec:
        for _ in range(count):
            out.append(_row(i, scorer, human_verdict=verdict, pre_label=pre))
            i += 1
    return out


# ---------------------------------------------------------------------------
# pending_rows
# ---------------------------------------------------------------------------


def test_pending_rows_are_unadjudicated_rows_that_still_carry_a_pre_label() -> None:
    rows = [
        _row(0, human_verdict=True),
        _row(1, human_verdict=None),
        _row(2, human_verdict=None, pre_label=None),  # drift-cleared: keep/flip refuses it
    ]
    assert [r.record_id for r in pending_rows(rows)] == ["case_001:tone_judge:0"]


# ---------------------------------------------------------------------------
# project_adjudication_yield
# ---------------------------------------------------------------------------


def test_a_push_that_clears_the_floor_reports_no_reason() -> None:
    rows = _rows([(30, None, False), (30, None, True), (5, True, True)])

    result = project_adjudication_yield("tone_judge", rows)

    assert result.pending_n == 60
    assert result.keep_all_minority_n == 30
    assert result.meets_floor is True
    assert result.flips_needed == 0
    assert result.reason == ""


def test_a_short_push_reports_the_flips_that_would_close_it() -> None:
    """20 pending FAIL against a large PASS majority: 5 more flips reach the floor."""
    rows = _rows([(20, None, False), (60, None, True)])

    result = project_adjudication_yield("tone_judge", rows)

    assert result.keep_all_minority_n == 20
    assert result.meets_floor is False
    assert result.flips_needed == MIN_MINORITY_LABELS - 20
    assert result.flips_available == 60
    assert "flips >=5" in result.reason


def test_all_pending_on_one_side_names_the_zero_and_stays_short() -> None:
    """The tone_judge shape: every pending pre-label is PASS, so no minority is created."""
    rows = _rows([(40, None, True), (2, True, True), (1, False, True)])

    result = project_adjudication_yield("tone_judge", rows)

    assert result.pending_pass == 40
    assert result.pending_fail == 0
    assert result.keep_all_minority_n == 1
    assert result.meets_floor is False
    assert "zero FAIL among them" in result.reason


def test_no_pending_rows_says_adjudication_cannot_move_it() -> None:
    rows = _rows([(20, True, True), (3, False, True)])

    result = project_adjudication_yield("tone_judge", rows)

    assert result.pending_n == 0
    assert result.meets_floor is False
    assert "no pending pre-labels" in result.reason
    assert "fresh labelling pass" in result.reason


def test_more_flips_needed_than_available_is_reported_as_unreachable() -> None:
    rows = _rows([(3, None, True), (30, True, True)])

    result = project_adjudication_yield("tone_judge", rows)

    assert result.flips_available == 3
    assert result.flips_needed > result.flips_available
    assert "not reachable by adjudication alone" in result.reason


def test_a_short_cluster_span_is_called_out_separately() -> None:
    """Enough minority items, but all in one case cluster — the second floor arm."""
    rows = [_row(i, human_verdict=None, pre_label=i % 2 == 0, case_id="case_solo") for i in range(60)]

    result = project_adjudication_yield("tone_judge", rows)

    assert result.keep_all_minority_n >= MIN_MINORITY_LABELS
    assert result.keep_all_n_clusters == 1
    assert result.meets_floor is False
    assert "cluster arm" in result.reason


def test_minority_is_fail_flips_when_passes_are_the_scarce_class() -> None:
    rows = _rows([(30, None, False), (2, None, True)])

    result = project_adjudication_yield("tone_judge", rows)

    assert result.minority_is_fail is False
    assert result.flips_available == result.pending_fail


# ---------------------------------------------------------------------------
# project_all / formatting / CLI
# ---------------------------------------------------------------------------


def test_project_all_derives_scorer_order_from_the_rows() -> None:
    rows = _rows([(1, True, True)], scorer="b_judge") + _rows([(1, True, True)], scorer="a_judge")

    assert [y.scorer for y in project_all(rows)] == ["b_judge", "a_judge"]


def test_project_all_honours_an_explicit_scorer_filter() -> None:
    rows = _rows([(1, True, True)], scorer="a_judge") + _rows([(1, True, True)], scorer="b_judge")

    assert [y.scorer for y in project_all(rows, ["b_judge"])] == ["b_judge"]


def test_format_table_marks_each_scorer_and_names_the_floor() -> None:
    clears = project_adjudication_yield("ok_judge", _rows([(30, None, False), (30, None, True)], "ok_judge"))
    short = project_adjudication_yield("bad_judge", _rows([(40, None, True)], "bad_judge"))

    table = format_yield_table([clears, short])

    assert f">={MIN_MINORITY_LABELS} minority labels" in table
    assert "[CLEARS FLOOR]" in table
    assert "[SHORT]" in table


def test_format_table_is_stable_for_an_empty_projection_list() -> None:
    assert "Adequacy floor" in format_yield_table([])


def test_main_reports_a_missing_labels_file_rather_than_raising(tmp_path: Path) -> None:
    assert main(["--file", str(tmp_path / "absent.jsonl")]) == 1


def test_main_prints_the_table_for_a_real_file(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    path = tmp_path / "labels.jsonl"
    rows = _rows([(30, None, False), (30, None, True)])
    path.write_text("\n".join(r.model_dump_json() for r in rows) + "\n", encoding="utf-8")

    exit_code = main(["--file", str(path)])

    assert exit_code == 0
    assert "[CLEARS FLOOR]" in capsys.readouterr().out


def test_the_yield_dataclass_is_frozen() -> None:
    result = AdjudicationYield(
        scorer="s", adjudicated_n=0, minority_n=0, n_clusters=0, pending_n=0,
        pending_pass=0, pending_fail=0, keep_all_minority_n=0, keep_all_n_clusters=0,
        meets_floor=False, flips_needed=0, flips_available=0,
    )
    try:
        result.scorer = "tampered"  # type: ignore[misc]
    except Exception as exc:  # dataclasses raises FrozenInstanceError
        assert "frozen" in type(exc).__name__.lower() or "frozen" in str(exc).lower()
    else:  # pragma: no cover - would mean the dataclass stopped being frozen
        raise AssertionError("AdjudicationYield must be frozen")
