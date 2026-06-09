"""
test_eval_summary.py - Unit tests for the eval-run headline metric + summary.

Exercises evals/summary.py, which is part of the standalone eval harness
(not under src/npc_engine). The evals directory is inserted onto sys.path
so the bare-name import convention used by the harness works under pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

_EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"
if str(_EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(_EVALS_DIR))

import summary  # noqa: E402  (path inserted above)


def _case(case_id: str, expectations: list[dict]) -> dict:
    return {
        "case_id": case_id,
        "description": "",
        "passed": all(e.get("passed", False) or e.get("skipped") for e in expectations),
        "expectations": expectations,
        "response": {"npc_response": "x"},
        "error": None,
    }


def _exp(kind: str, passed: bool, skipped: bool = False) -> dict:
    return {"kind": kind, "passed": passed, "skipped": skipped, "detail": ""}


def test_summarize_all_pass_headline_is_zero() -> None:
    results = [
        _case("case_adv_roleplay_swap", [_exp("schema", True), _exp("keyword_none", True)]),
        _case("case_neg_aldric_no_troop_knowledge", [_exp("keyword_none", True)]),
    ]
    s = summary.summarize(results)
    assert s.hallucination_failures == 0
    assert s.guard_cases == 2
    assert s.guard_turns == 2
    assert "0 lore hallucinations" in s.headline
    assert "across 2 adversarial turns" in s.headline


def test_keyword_none_failure_in_guard_case_is_hallucination() -> None:
    results = [
        _case("case_adv_leading_betrayal", [_exp("schema", True), _exp("keyword_none", False)]),
    ]
    s = summary.summarize(results)
    assert s.hallucination_failures == 1
    assert s.keyword_none_failures == 1
    assert "1 lore hallucination " in s.headline  # singular, no trailing 's'


def test_skipped_case_not_counted_as_turn() -> None:
    results = [
        _case("case_neg_lira_no_system_reveal", [_exp("runner", True, skipped=True)]),
        _case("case_adv_false_premise_peace", [_exp("keyword_none", True)]),
    ]
    s = summary.summarize(results)
    assert s.skipped_cases == 1
    assert s.total_cases == 2
    assert s.total_turns == 1
    assert s.guard_turns == 1  # the skipped guard case does not count as an evaluated turn


def test_failure_breakdown_by_kind() -> None:
    results = [
        _case("case_adv_x", [_exp("schema", False)]),
        _case("case_neg_y", [_exp("keyword_none", False)]),
        _case("case_voice_z", [_exp("tone_judge", False)]),
        _case("case_003_trade", [_exp("in_set", False)]),
    ]
    s = summary.summarize(results)
    assert s.schema_failures == 1
    assert s.keyword_none_failures == 1
    assert s.tone_judge_failures == 1
    assert s.other_failures == 1


def test_affirms_judge_failure_in_guard_case_is_hallucination() -> None:
    # An affirms_judge failure inside a guard case must count toward the headline
    # lore-hallucination number — not just literal keyword_none hits.
    results = [
        _case("case_neg_aldric_no_war_outcome", [_exp("schema", True), _exp("affirms_judge", False)]),
    ]
    s = summary.summarize(results)
    assert s.affirms_judge_failures == 1
    assert s.hallucination_failures == 1
    assert "1 lore hallucination " in s.headline
    assert s.guarantee_demonstrated is False


def test_non_guard_affirms_judge_failure_not_a_hallucination() -> None:
    results = [
        _case("case_pos_lira_fence_trade", [_exp("affirms_judge", False)]),
    ]
    s = summary.summarize(results)
    assert s.affirms_judge_failures == 1
    assert s.hallucination_failures == 0


def test_non_guard_keyword_none_failure_not_a_hallucination() -> None:
    # A positive (non-guard) case using keyword_none should count toward
    # keyword_none_failures but NOT toward the lore-hallucination headline.
    results = [
        _case("case_pos_world_blight_guard", [_exp("keyword_none", False)]),
    ]
    s = summary.summarize(results)
    assert s.keyword_none_failures == 1
    assert s.hallucination_failures == 0
    assert s.guard_cases == 0


def test_zero_guard_turns_headline_is_not_vacuously_green() -> None:
    # No guard case ran (all skipped): the headline must NOT read "0 lore hallucinations".
    results = [
        _case("case_adv_roleplay_swap", [_exp("runner", True, skipped=True)]),
        _case("case_neg_lira_no_system_reveal", [_exp("runner", True, skipped=True)]),
    ]
    s = summary.summarize(results)
    assert s.guard_turns == 0
    assert s.guarantee_demonstrated is False
    assert "0 lore hallucinations" not in s.headline
    assert "guarantee not demonstrated" in s.headline


def test_guarantee_demonstrated_true_when_guard_turn_clean() -> None:
    results = [_case("case_adv_x", [_exp("keyword_none", True)])]
    s = summary.summarize(results)
    assert s.guarantee_demonstrated is True


def test_guarantee_not_demonstrated_when_hallucination_present() -> None:
    results = [_case("case_adv_x", [_exp("keyword_none", False)])]
    s = summary.summarize(results)
    assert s.guarantee_demonstrated is False


def test_format_summary_lines_contains_headline() -> None:
    results = [_case("case_adv_x", [_exp("keyword_none", True)])]
    s = summary.summarize(results)
    lines = summary.format_summary_lines(s)
    blob = "\n".join(lines)
    assert s.headline in blob
    assert "schema failures" in blob
    assert "tone_judge failures" in blob


def test_format_summary_markdown_contains_headline() -> None:
    results = [_case("case_adv_x", [_exp("keyword_none", True)])]
    s = summary.summarize(results)
    md = summary.format_summary_markdown(s)
    blob = "\n".join(md)
    assert s.headline in blob
    assert blob.lstrip().startswith("##")


def test_write_report_embeds_guarantee_section(tmp_path) -> None:
    import report  # noqa: PLC0415  (eval harness module, path inserted at top)

    results = [
        _case("case_adv_roleplay_swap", [_exp("schema", True), _exp("keyword_none", True)]),
        _case("case_neg_lira_no_system_reveal", [_exp("keyword_none", True)]),
    ]
    report_path = report.write_report(results=results, output_dir=tmp_path)
    text = report_path.read_text(encoding="utf-8")
    assert "Anti-Hallucination Guarantee" in text
    assert "0 lore hallucinations across 2 adversarial turns" in text
