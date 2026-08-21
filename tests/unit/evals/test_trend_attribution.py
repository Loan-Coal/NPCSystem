"""
Module: tests.unit.evals.test_trend_attribution
Layer: test (unit)
Purpose: A trend row and a comparison report must say WHICH VARIANT produced the number.
         Without this, six weeks of trend rows cannot answer "which prompt version / which
         retrieval profile produced which result", and an A/B verdict names two gen_ids
         without naming what differed between them.
Dependencies: pytest; evals.trend_store, evals.run_identity
Used by: make test (pytest discovery)

Why attribution is a correctness property, not an ergonomic one. compare.py already refuses
INCOMPARABLE runs (harness_version, judge_model, k). What it never did is state what was
DELIBERATELY varied. A reader of the report cannot distinguish "these two arms differ only in
retrieval_profile" from "somebody also edited the engine", so a confident McNemar verdict can
be attached to the wrong cause.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from trend_store import TrendRow  # noqa: E402


def _row(**overrides: object) -> TrendRow:
    base: dict[str, object] = {"gen_id": "k3_abc", "harness_version": "deadbeef1234", "recorded_at": "2026-08-21T00:00:00Z"}
    base.update(overrides)
    return TrendRow(**base)  # type: ignore[arg-type]


def test_trend_row_records_the_variant_that_produced_it() -> None:
    row = _row(
        retrieval_profile="aggressive",
        dialogue_prompt_hash="aaaa1111bbbb",
        git_sha="1234567",
        prompt_token_budget=512,
    )

    assert row.retrieval_profile == "aggressive"
    assert row.dialogue_prompt_hash == "aaaa1111bbbb"
    assert row.git_sha == "1234567"
    assert row.prompt_token_budget == 512


def test_trend_row_records_retrieval_precision() -> None:
    """`evals retrieval` printed precision@k to stdout and persisted nothing, so retrieval
    quality was the one metric that could never be trended or gated."""
    assert _row(mean_precision_at_k=0.31).mean_precision_at_k == 0.31


def test_attribution_fields_default_so_existing_rows_still_load() -> None:
    """The store is append-only and holds rows written before these fields existed."""
    row = _row()

    assert row.retrieval_profile is None
    assert row.dialogue_prompt_hash is None
    assert row.git_sha is None
    assert row.prompt_token_budget is None
    assert row.mean_precision_at_k is None


def test_run_identity_names_the_fields_that_differ_between_two_arms() -> None:
    from run_variance import describe_variant_delta  # noqa: E402

    before = {"retrieval_profile": "default", "dialogue_prompt_hash": "aaaa", "git_sha": "111"}
    after = {"retrieval_profile": "aggressive", "dialogue_prompt_hash": "aaaa", "git_sha": "111"}

    delta = describe_variant_delta(before, after)

    assert "retrieval_profile" in delta
    assert "default" in delta and "aggressive" in delta
    assert "dialogue_prompt_hash" not in delta  # unchanged fields are not noise


def test_identical_arms_report_no_delta_explicitly() -> None:
    """A no-op comparison must SAY it is a no-op. Printing nothing reads as 'not checked'."""
    from run_variance import NO_VARIANT_DELTA, describe_variant_delta  # noqa: E402

    same = {"retrieval_profile": "default", "git_sha": "111"}

    assert describe_variant_delta(same, dict(same)) == NO_VARIANT_DELTA


def test_a_missing_field_on_one_side_is_reported_not_hidden() -> None:
    """An older arm lacking a field is a real comparability caveat, not an equality."""
    from run_variance import describe_variant_delta  # noqa: E402

    delta = describe_variant_delta({"git_sha": "111"}, {"git_sha": "111", "retrieval_profile": "x"})

    assert "retrieval_profile" in delta
