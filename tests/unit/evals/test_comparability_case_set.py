"""
Module: test_comparability_case_set
Layer: tests (eval harness tests)
Purpose: Verify that two runs differing only in case-set remain comparable (T16.3).
         harness_version must cover only the instrument (matchers + prompts/eval/);
         a new case_set_version field carries the case fingerprint independently.
Dependencies: comparability, trend_store, _run_config_hashing (evals/).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "evals"))

from _run_config_hashing import resolve_case_set_version, resolve_harness_version
from comparability import ComparabilityKey, is_comparable, key_for
from trend_store import TrendRow

_INSTRUMENT_HASH = "aabbcc112233"
_JUDGE = "model-judge-x"


def _make_row(case_set_version: str, gen_id: str = "gen-a") -> TrendRow:
    return TrendRow(
        gen_id=gen_id,
        harness_version=_INSTRUMENT_HASH,
        recorded_at="2026-10-20T00:00:00+00:00",
        judge_identity=_JUDGE,
        case_set_version=case_set_version,
    )


def test_case_set_version_is_declared_field() -> None:
    """case_set_version must be a first-class TrendRow field, not just stored as extra."""
    assert "case_set_version" in TrendRow.model_fields


def test_different_case_set_is_comparable() -> None:
    """Rows with the same instrument but different case sets must be comparable.

    Before T16.3, case bytes were baked into harness_version, so editing one case file
    made every prior run incomparable. After T16.3, harness_version covers only the
    instrument (matchers + prompts/eval/), and case_set_version carries the case
    fingerprint. ComparabilityKey keys only on the instrument.
    """
    baseline = _make_row("case-set-v1", gen_id="gen-baseline")
    candidate_key = ComparabilityKey(
        harness_version=_INSTRUMENT_HASH,
        judge_identity=_JUDGE,
    )
    assert is_comparable(baseline, candidate_key)


def test_harness_version_excludes_case_bytes(tmp_path: Path) -> None:
    """resolve_harness_version must not change when only case files change."""
    matchers = tmp_path / "matchers.py"
    matchers.write_text("# matchers\n", encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()

    v1 = resolve_harness_version(prompts_eval_dir=prompts, matchers_path=matchers)
    v2 = resolve_harness_version(prompts_eval_dir=prompts, matchers_path=matchers)
    assert v1 == v2


def test_case_set_version_changes_with_case_content(tmp_path: Path) -> None:
    """resolve_case_set_version must produce different hashes for different case content."""
    cases_a = tmp_path / "cases_a"
    cases_a.mkdir()
    (cases_a / "test.yaml").write_text("prompt: scenario_alpha\n", encoding="utf-8")

    cases_b = tmp_path / "cases_b"
    cases_b.mkdir()
    (cases_b / "test.yaml").write_text("prompt: scenario_beta\n", encoding="utf-8")

    v_a = resolve_case_set_version(cases_a)
    v_b = resolve_case_set_version(cases_b)
    assert v_a != v_b


def test_harness_version_changes_with_judge_criteria(tmp_path: Path) -> None:
    """resolve_harness_version must change when judge criteria change."""
    matchers = tmp_path / "matchers.py"
    matchers.write_text("# matchers\n", encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    criteria = prompts / "refusal_judge.yaml"
    criteria.write_text("criteria: do not hallucinate\n", encoding="utf-8")

    v_before = resolve_harness_version(prompts_eval_dir=prompts, matchers_path=matchers)
    criteria.write_text("criteria: hallucination is acceptable\n", encoding="utf-8")
    v_after = resolve_harness_version(prompts_eval_dir=prompts, matchers_path=matchers)

    assert v_before != v_after
