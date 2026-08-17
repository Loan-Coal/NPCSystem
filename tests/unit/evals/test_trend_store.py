"""
Module: test_trend_store
Layer: test (unit)
Purpose: RED anchor + behaviour tests for evals/trend_store.py — append-only
         JSONL trend storage keyed by gen_id (EVAL-P23.1).
Dependencies: pytest; trend_store (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trend_store import (
    DuplicateGenIdError,
    RateWithCI,
    ScorerKappa,
    TrendRow,
    append_trend_row,
    latest_row,
    read_trend_rows,
    rows_for_scorer,
)


def _row(gen_id: str, **overrides: object) -> TrendRow:
    base: dict[str, object] = dict(
        gen_id=gen_id,
        harness_version="v1",
        recorded_at="2026-08-17T00:00:00+00:00",
        guard=RateWithCI(rate=0.9, ci_low=0.8, ci_high=0.95, n=94),
        capability=RateWithCI(rate=0.85, ci_low=0.7, ci_high=0.92, n=48),
        inconclusive_rate=0.0,
        scorer_kappas=(ScorerKappa(scorer="tone_judge", kappa=0.9, ci_low=0.8, ci_high=0.95, n=135),),
    )
    base.update(overrides)
    return TrendRow(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_recording_an_existing_gen_id_raises_rather_than_duplicating(tmp_path: Path) -> None:
    """The store is append-only — a run's numbers must not silently change
    after the fact by re-recording the same gen_id with different values."""
    path = tmp_path / "trend.jsonl"
    append_trend_row(_row("gen_a"), path)
    with pytest.raises(DuplicateGenIdError, match="gen_a"):
        append_trend_row(_row("gen_a", inconclusive_rate=0.5), path)
    # the original row must be unaffected by the refused write
    rows = read_trend_rows(path)
    assert len(rows) == 1
    assert rows[0].inconclusive_rate == 0.0


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------


def test_append_and_read_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "trend.jsonl"
    append_trend_row(_row("gen_a"), path)
    append_trend_row(_row("gen_b"), path)
    rows = read_trend_rows(path)
    assert [r.gen_id for r in rows] == ["gen_a", "gen_b"]


def test_read_missing_file_returns_empty_list(tmp_path: Path) -> None:
    assert read_trend_rows(tmp_path / "does_not_exist.jsonl") == []


def test_latest_row_is_most_recently_appended(tmp_path: Path) -> None:
    path = tmp_path / "trend.jsonl"
    append_trend_row(_row("gen_a"), path)
    append_trend_row(_row("gen_b"), path)
    assert latest_row(path).gen_id == "gen_b"


def test_latest_row_none_when_store_empty(tmp_path: Path) -> None:
    assert latest_row(tmp_path / "does_not_exist.jsonl") is None


def test_store_survives_a_schema_addition_unknown_fields_load(tmp_path: Path) -> None:
    """A row written by a NEWER harness version, carrying a field this
    reader's TrendRow doesn't declare, must still load rather than raise."""
    path = tmp_path / "trend.jsonl"
    row_with_extra = _row("gen_a").model_dump()
    row_with_extra["a_field_from_the_future"] = "some new metric"
    path.write_text(json.dumps(row_with_extra) + "\n", encoding="utf-8")
    rows = read_trend_rows(path)
    assert rows[0].gen_id == "gen_a"


def test_store_survives_a_row_missing_a_newer_field(tmp_path: Path) -> None:
    """A row written by an OLDER harness version, before panel_agreement_rate
    existed, must still load — every optional field defaults."""
    path = tmp_path / "trend.jsonl"
    old_row = {
        "gen_id": "gen_old",
        "harness_version": "v0",
        "recorded_at": "2026-01-01T00:00:00+00:00",
    }
    path.write_text(json.dumps(old_row) + "\n", encoding="utf-8")
    rows = read_trend_rows(path)
    assert rows[0].gen_id == "gen_old"
    assert rows[0].guard is None
    assert rows[0].panel_agreement_rate is None


def test_rows_for_scorer_filters_across_runs(tmp_path: Path) -> None:
    path = tmp_path / "trend.jsonl"
    append_trend_row(
        _row("gen_a", scorer_kappas=(
            ScorerKappa(scorer="tone_judge", kappa=0.9, ci_low=0.8, ci_high=0.95, n=135),
            ScorerKappa(scorer="refusal_judge", kappa=0.25, ci_low=0.1, ci_high=0.4, n=75),
        )),
        path,
    )
    append_trend_row(
        _row("gen_b", scorer_kappas=(
            ScorerKappa(scorer="tone_judge", kappa=0.88, ci_low=0.78, ci_high=0.94, n=140),
        )),
        path,
    )
    rows = read_trend_rows(path)
    tone_history = rows_for_scorer("tone_judge", rows)
    assert [k.kappa for k in tone_history] == [0.9, 0.88]
    refusal_history = rows_for_scorer("refusal_judge", rows)
    assert len(refusal_history) == 1  # gen_b never calibrated it — silently absent
