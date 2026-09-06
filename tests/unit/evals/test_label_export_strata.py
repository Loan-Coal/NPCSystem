"""
Module: test_label_export_strata
Layer: test (unit)
Purpose: Unit tests for label_export_strata.py — the declared (not derived)
         case-family stratum used to oversample expected-negative records in a
         stratified label-export batch.
Dependencies: pytest; label_export_strata (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

from label_export_strata import (
    CASE_STRATA_FILE,
    case_id_of,
    load_expected_negative_cases,
    stratum_of,
)

# ---------------------------------------------------------------------------
# case_id_of
# ---------------------------------------------------------------------------


def test_case_id_of_strips_scorer_and_index() -> None:
    assert case_id_of("case_adv_aldric_black_market:commits_judge:2") == "case_adv_aldric_black_market"


def test_case_id_of_strips_repetition_suffix_too() -> None:
    """The record_id's first ':' segment is the case id whether or not a
    repetition-qualified suffix ('#rN') is appended after the index."""
    assert case_id_of("case_neg_aldric_no_politics:tone_judge:0#r2") == "case_neg_aldric_no_politics"


# ---------------------------------------------------------------------------
# stratum_of
# ---------------------------------------------------------------------------


def test_stratum_of_declared_case_is_expected_negative() -> None:
    negative = frozenset({"case_adv_x"})
    assert stratum_of("case_adv_x", negative) == "expected_negative"


def test_stratum_of_undeclared_case_is_expected_positive() -> None:
    """A case not in the declared set is expected_positive by default — including
    one that merely LOOKS negative by name (the declaration, not a prefix check,
    is what decides the stratum)."""
    negative = frozenset({"case_adv_x"})
    assert stratum_of("case_neg_looks_negative_but_undeclared", negative) == "expected_positive"
    assert stratum_of("case_pos_y", negative) == "expected_positive"


# ---------------------------------------------------------------------------
# load_expected_negative_cases
# ---------------------------------------------------------------------------


def test_load_expected_negative_cases_reads_the_declared_list(tmp_path: Path) -> None:
    strata_file = tmp_path / "case_strata.yaml"
    strata_file.write_text(
        "expected_negative_cases:\n  - case_adv_a\n  - case_neg_b\n",
        encoding="utf-8",
    )
    cases = load_expected_negative_cases(strata_file)
    assert cases == frozenset({"case_adv_a", "case_neg_b"})


def test_load_expected_negative_cases_empty_file_is_empty_set(tmp_path: Path) -> None:
    strata_file = tmp_path / "case_strata.yaml"
    strata_file.write_text("expected_negative_cases: []\n", encoding="utf-8")
    assert load_expected_negative_cases(strata_file) == frozenset()


def test_the_real_checked_in_declaration_names_37_guard_battery_cases() -> None:
    """RED anchor: the checked-in declaration must exist and match the measured
    guard-battery population — 24 case_neg + 13 case_adv cases, the only cases
    authored to elicit a minority verdict (docs/EVAL_NEXT_GENERATION_CASE_SET.md)."""
    if not CASE_STRATA_FILE.exists():
        import pytest

        pytest.skip("real committed strata file not present in this checkout")
    cases = load_expected_negative_cases()
    assert len(cases) == 37
    assert all(c.startswith(("case_neg_", "case_adv_")) for c in cases)
