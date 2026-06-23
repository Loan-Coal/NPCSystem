"""
test_eval_runner_guards.py - Unit tests for the runner's guard auto-injection.

Verifies that every adversarial/negative case gets the universal anti-hallucination
guards (substantive length, no canned fallback, in-character) appended, while
ordinary cases are left untouched. Pure-function tests — no server or LLM.
"""

from __future__ import annotations

# evals/ is on pytest's pythonpath via pyproject.
import runner


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


def test_demo_world_guard_case_gets_lore_affirms_judge() -> None:
    # Demo world is epoch=war: guard cases also get the lore affirmation judge.
    case = {"case_id": "case_neg_aldric_no_war_outcome", "seed": {"requires_world": "demo"}}
    expected = runner._expected_with_guards(case)
    lore = [e for e in expected if e["kind"] == "affirms_judge"]
    assert len(lore) == 1
    assert lore[0]["description"] == runner._GUARD_LORE_RUBRIC


def test_non_demo_guard_case_has_no_lore_judge() -> None:
    # Peacetime eval worlds must not get the war-over lore judge (no false fires).
    case = {"case_id": "case_neg_z", "seed": {"requires_world": "village"}}
    kinds = [e["kind"] for e in runner._expected_with_guards(case)]
    assert "affirms_judge" not in kinds
