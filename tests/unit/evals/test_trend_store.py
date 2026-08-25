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

from panel_metric_records import CriterionKappa, PanelKappa, RepeatFlips
from comparability import ComparabilityKey, key_for
from trend_store import (
    DuplicateGenIdError,
    RateWithCI,
    ScorerKappa,
    TrendRow,
    append_trend_row,
    latest_comparable_row,
    latest_row,
    read_trend_rows,
    rows_for_scorer,
)


def _row(gen_id: str, **overrides: object) -> TrendRow:
    base: dict[str, object] = dict(
        gen_id=gen_id,
        harness_version="v1",
        judge_identity="panel:llama3.1:8b+mixtral:8x7b",
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


# ---------------------------------------------------------------------------
# latest_comparable_row — EVAL-P23 Defect B
# ---------------------------------------------------------------------------


def _key(harness_version: str = "v1", judge: str = "panel:llama3.1:8b+mixtral:8x7b") -> ComparabilityKey:
    return ComparabilityKey(harness_version=harness_version, judge_identity=judge)


def test_latest_comparable_row_skips_rows_from_another_harness_version(tmp_path: Path) -> None:
    """harness_version hashes evals/cases/, prompts/eval/ and matchers.py, so a
    case or judge-criterion edit changes it. The most recent row under a
    different version is not a baseline — walk back to one that is."""
    path = tmp_path / "trend.jsonl"
    append_trend_row(_row("gen_a", harness_version="v1"), path)
    append_trend_row(_row("gen_b", harness_version="v2"), path)
    chosen = latest_comparable_row(_key("v1"), path)
    assert chosen is not None
    assert chosen.gen_id == "gen_a"
    assert latest_row(path).gen_id == "gen_b"  # latest_row keeps its meaning


def test_latest_comparable_row_skips_rows_scored_by_another_judge(tmp_path: Path) -> None:
    """DEC-190's constraint, which lived only in compare.py: two arms scored by
    different instruments are not comparable. The trend gate is declared
    AUTHORITATIVE over compare by Run-EvalHarness.ps1, so it checking only
    harness_version let a panel-scored baseline gate a single-judge candidate —
    the delta then contains the instrument change, not just the engine."""
    path = tmp_path / "trend.jsonl"
    append_trend_row(_row("gen_panel", judge_identity="panel:llama3.1:8b+mixtral:8x7b"), path)
    append_trend_row(_row("gen_single", judge_identity="mixtral:8x7b"), path)

    chosen = latest_comparable_row(_key(judge="panel:llama3.1:8b+mixtral:8x7b"), path)
    assert chosen is not None
    assert chosen.gen_id == "gen_panel"

    single = latest_comparable_row(_key(judge="mixtral:8x7b"), path)
    assert single is not None
    assert single.gen_id == "gen_single"


def test_a_row_with_no_recorded_judge_is_comparable_to_nothing(tmp_path: Path) -> None:
    """An unknown instrument is refused rather than assumed to match. The store is
    empty today, so strictness costs nothing and prevents a legacy row from
    silently serving as a cross-instrument baseline later."""
    path = tmp_path / "trend.jsonl"
    append_trend_row(_row("gen_unknown", judge_identity=""), path)
    assert latest_comparable_row(_key(), path) is None
    assert latest_comparable_row(ComparabilityKey(harness_version="v1", judge_identity=""), path) is None


def test_latest_comparable_row_is_none_when_nothing_matches(tmp_path: Path) -> None:
    path = tmp_path / "trend.jsonl"
    append_trend_row(_row("gen_a", harness_version="v1"), path)
    assert latest_comparable_row(_key("v3"), path) is None


def test_latest_comparable_row_on_an_empty_store_is_none(tmp_path: Path) -> None:
    assert latest_comparable_row(_key(), tmp_path / "does_not_exist.jsonl") is None


def test_key_for_reads_both_dimensions_off_a_row(tmp_path: Path) -> None:
    """The key a candidate is gated with comes from the candidate's own row, so the
    two cannot disagree about what "comparable" meant."""
    row = _row("gen_a", harness_version="hv", judge_identity="panel:a+b")
    assert key_for(row) == ComparabilityKey(harness_version="hv", judge_identity="panel:a+b")


# ---------------------------------------------------------------------------
# Panel kappa on the row — EVAL-P23 Defect D
# ---------------------------------------------------------------------------


def test_trend_row_records_kappa_and_per_criterion_breakdown(tmp_path: Path) -> None:
    """A trend built on raw pairwise agreement tracks a number inflated by the
    pass base rate (0.956 raw vs 0.526 kappa on the real corpus, DEC-188). The
    row must carry the chance-corrected number, its per-criterion breakdown and
    the repeat-flip counts, and survive a round trip through the store."""
    path = tmp_path / "trend.jsonl"
    row = _row(
        "gen_panel",
        panel_agreement_rate=0.9556,
        panel_kappa=PanelKappa(kappa=0.5256, ci_low=0.227, ci_high=0.730, n_items=345),
        kappa_by_criterion=(
            CriterionKappa(judge_kind="tone_judge", kappa=1.0, n_items=135, unanimous=135),
            CriterionKappa(judge_kind="refusal_judge", kappa=0.225, n_items=75, unanimous=60),
        ),
        repeat_flips=RepeatFlips(records_with_flips=12, unanimous_flips=4, solo_flips=8, n_records=115),
    )
    append_trend_row(row, path)

    loaded = read_trend_rows(path)[0]
    assert loaded.panel_agreement_rate == 0.9556  # kept — existing rows must not break
    assert loaded.panel_kappa is not None
    assert loaded.panel_kappa.kappa == 0.5256
    assert loaded.panel_kappa.ci_low == 0.227
    assert {c.judge_kind: c.kappa for c in loaded.kappa_by_criterion} == {
        "tone_judge": 1.0, "refusal_judge": 0.225,
    }
    assert loaded.repeat_flips is not None
    assert loaded.repeat_flips.solo_flips == 8  # judge-driven flips, distinct from engine ones


def test_a_row_without_panel_kappa_still_loads(tmp_path: Path) -> None:
    """A single-judge run records no panel kappa; that is a valid state."""
    path = tmp_path / "trend.jsonl"
    append_trend_row(_row("gen_single"), path)
    loaded = read_trend_rows(path)[0]
    assert loaded.panel_kappa is None
    assert loaded.kappa_by_criterion == ()
    assert loaded.repeat_flips is None
