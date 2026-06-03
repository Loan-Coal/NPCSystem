"""
test_eval_runner_guards.py - Unit tests for the runner's guard auto-injection.

Verifies that every adversarial/negative case gets the universal anti-hallucination
guards (substantive length, no canned fallback, in-character) appended, while
ordinary cases are left untouched. Pure-function tests — no server or LLM.
"""

from __future__ import annotations

import sys
from pathlib import Path

_EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"
if str(_EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(_EVALS_DIR))

import runner  # noqa: E402  (path inserted above)


def test_is_guard_case() -> None:
    assert runner._is_guard_case("case_adv_leading_betrayal") is True
    assert runner._is_guard_case("case_neg_aldric_no_politics") is True
    assert runner._is_guard_case("case_001_grieving_elder") is False
    assert runner._is_guard_case("case_voice_mira") is False


def test_fallback_lines_loaded() -> None:
    assert "I need a moment to think." in runner._FALLBACK_LINES
    assert "Move along, citizen." in runner._FALLBACK_LINES


def test_guard_case_gets_universal_guards_appended() -> None:
    case = {"case_id": "case_adv_x", "expected": [{"kind": "keyword_none", "keywords": ["x"]}]}
    expected = runner._expected_with_guards(case)
    kinds = [e["kind"] for e in expected]
    assert kinds[0] == "keyword_none"  # original preserved first
    assert "min_length" in kinds
    assert "tone_judge" in kinds
    # exactly one keyword_none carries the fallback lines
    fallback_block = [e for e in expected if e["kind"] == "keyword_none" and "I need a moment to think." in e.get("keywords", [])]
    assert len(fallback_block) == 1


def test_non_guard_case_unchanged() -> None:
    case = {"case_id": "case_003_trade", "expected": [{"kind": "schema"}]}
    assert runner._expected_with_guards(case) == [{"kind": "schema"}]


def test_guard_case_without_declared_expectations_still_guarded() -> None:
    case = {"case_id": "case_neg_y"}
    kinds = [e["kind"] for e in runner._expected_with_guards(case)]
    assert kinds == ["min_length", "keyword_none", "tone_judge"]
