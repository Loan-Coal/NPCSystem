"""
Module: test_base_rate_matches_its_corpus
Layer: tests (unit)
Purpose: RED anchor for ISSUE-253 — mde.RECORDED_BASE_RATE must equal the pass rate of
         the generation the recorded kappas were measured on. The constant read 0.951,
         which was correct against judged.jsonl.pre-panel-20260817_192458.bak (328/345)
         and went stale when the 2026-08-18 panel re-judge flipped one record to 329/345.
Dependencies: pytest; mde, verdict_sources, rate_stats (evals/)
Used by: `make test`, `make check` via test-cov-evals.
"""

from __future__ import annotations

from pathlib import Path

from mde import KAPPA_GENERATION, RECORDED_BASE_RATE
from rate_stats import pass_rate
from verdict_sources import judged_rows

REPO_ROOT = Path(__file__).resolve().parents[3]


def _corpus_pass_rate() -> float:
    """Pass rate over the LLM-judged rows of the generation the kappas came from."""
    rows = judged_rows(REPO_ROOT / "evals" / "generations" / KAPPA_GENERATION)
    return pass_rate(sum(1 for r in rows if r.passed), len(rows))


def test_recorded_base_rate_equals_its_corpus() -> None:
    """RED anchor. Measured 2026-09-01: constant 0.951 vs corpus 0.9536 (329/345)."""
    assert round(RECORDED_BASE_RATE, 3) == round(_corpus_pass_rate(), 3), (
        f"mde.py records {RECORDED_BASE_RATE}, {KAPPA_GENERATION} measures "
        f"{_corpus_pass_rate():.4f}"
    )


def test_the_kappa_generation_exists_and_is_judged() -> None:
    """The corpus the base rate and the kappas are both attributed to is present."""
    rows = judged_rows(REPO_ROOT / "evals" / "generations" / KAPPA_GENERATION)
    assert len(rows) == 345, f"expected the 345 judged records ISSUE-184 used, got {len(rows)}"


def test_judged_rows_reads_only_the_llm_judged_file(tmp_path: Path) -> None:
    """judged_rows is the LLM-judged population, not the unified one.

    The base rate documents "the records kappa was measured on", and kappa is measured
    over judge verdicts. Deterministic matcher rows are a different population.
    """
    (tmp_path / "judged.jsonl").write_text(
        '{"record_id": "c:tone_judge:0", "case_id": "c", "judge_kind": "tone_judge",'
        ' "passed": true, "repetition": 0}\n', encoding="utf-8")
    (tmp_path / "deterministic_judged.jsonl").write_text(
        '{"record_id": "c:schema:0", "matcher_kind": "schema", "passed": false,'
        ' "repetition": 0}\n', encoding="utf-8")
    rows = judged_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0].source == "judged"
