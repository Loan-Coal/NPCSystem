"""
test_eval_summary.py - Unit tests for the eval-run headline metric + summary.

Exercises evals/summary.py, which is part of the standalone eval harness
(not under src/npc_engine). The evals/ directory is on pytest's pythonpath
(pyproject) so the harness's bare-name imports resolve.
"""

from __future__ import annotations

import pytest

# evals/ is on pytest's pythonpath via pyproject.
import summary


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
    results = [
        _case("case_adv_x", [_exp("keyword_none", True)]),
        _case("case_pos_x", [_exp("affirms_judge", True)]),  # paired capability case required
    ]
    s = summary.summarize(results)
    lines = summary.format_summary_lines(s)
    blob = "\n".join(lines)
    assert s.headline in blob
    assert "schema failures" in blob
    assert "tone_judge failures" in blob


def test_format_summary_markdown_contains_headline() -> None:
    results = [
        _case("case_adv_x", [_exp("keyword_none", True)]),
        _case("case_pos_x", [_exp("affirms_judge", True)]),  # paired capability case required
    ]
    s = summary.summarize(results)
    md = summary.format_summary_markdown(s)
    blob = "\n".join(md)
    assert s.headline in blob
    assert blob.lstrip().startswith("##")


def test_skipped_cases_excluded_from_evaluated_denominator() -> None:
    """49 evaluated / 53 total — skipped cases excluded from the evaluated denominator.

    53 cases total (48 cap + 1 guard evaluated, 4 skipped) → evaluated_cases must be 49.
    No summary line may quote 53 as a pass-rate denominator.
    """
    cap = [_case(f"case_pos_{i:02d}", [_exp("schema", True)]) for i in range(48)]
    guard = [_case("case_adv_g00", [_exp("keyword_none", True)])]  # 1 evaluated guard case
    skipped = [_case(f"case_skip_{i:02d}", [_exp("runner", True, skipped=True)]) for i in range(4)]
    results = cap + guard + skipped
    assert len(results) == 53
    s = summary.summarize(results)
    assert s.evaluated_cases == 49
    lines = summary.format_summary_lines(s)
    blob = "\n".join(lines)
    assert "49 evaluated" in blob
    assert "53 total" in blob


def test_capability_and_guard_rates_are_reported_separately() -> None:
    """40 guard + 42 capability cases → two separate rates, n's, and Wilson intervals."""
    guard = [
        _case(f"case_adv_{i:02d}", [_exp("keyword_none", i % 5 != 0)]) for i in range(20)
    ] + [
        _case(f"case_neg_{i:02d}", [_exp("keyword_none", i % 4 != 0)]) for i in range(20)
    ]
    cap = [
        _case(f"case_pos_{i:02d}", [_exp("affirms_judge", i % 3 != 0)]) for i in range(42)
    ]
    results = guard + cap

    s = summary.summarize(results)

    assert s.guard_cases == 40, "the COUNT still spans both populations (conservation)"
    assert s.adversarial_cases == 40, "this fixture has no ah_demo_ cases"
    assert s.capability_cases == 42
    assert s.guard_turns == 40
    assert s.capability_turns == 42
    assert s.adversarial_rate is not None
    assert s.capability_rate is not None
    # Guard: 31 passes (16 adv + 15 neg); cap: 28 passes → different rates
    assert s.adversarial_rate != s.capability_rate
    assert 0.0 <= s.adversarial_ci_low <= s.adversarial_rate <= s.adversarial_ci_high <= 1.0
    assert 0.0 <= s.capability_ci_low <= s.capability_rate <= s.capability_ci_high <= 1.0


def test_unclassifiable_case_raises() -> None:
    """A case_id matching no battery and no excluded list raises in classify_battery."""
    import case_stats

    with pytest.raises(ValueError, match="totally_unknown_prefix_123"):
        case_stats.classify_battery("totally_unknown_prefix_123")


def test_unclassified_case_id_raises_in_summarize() -> None:
    """summarize() must raise ValueError for a case_id matching no known prefix.

    The existing test_unclassifiable_case_raises verifies classify_battery raises
    in isolation; this test verifies the production path (summarize) actually calls it.
    RED anchor: fails before the fix because summarize never calls classify_battery.
    """
    results = [
        _case("totally_unknown_prefix_123", [_exp("schema", False)]),
    ]
    with pytest.raises(ValueError, match="totally_unknown_prefix_123"):
        summary.summarize(results)


def test_write_report_embeds_guarantee_section(tmp_path) -> None:
    import report  # noqa: PLC0415  (eval harness module, path inserted at top)

    results = [
        _case("case_adv_roleplay_swap", [_exp("schema", True), _exp("keyword_none", True)]),
        _case("case_neg_lira_no_system_reveal", [_exp("keyword_none", True)]),
        _case("case_pos_mira_trade", [_exp("affirms_judge", True)]),
    ]
    report_path = report.write_report(results=results, output_dir=tmp_path)
    text = report_path.read_text(encoding="utf-8")
    assert "Anti-Hallucination Guarantee" in text
    assert "0 lore hallucinations across 2 adversarial turns" in text


def test_summary_without_capability_rate_raises() -> None:
    """format_summary_lines must raise when a guard rate is set but capability_rate is absent."""
    results = [
        _case("case_adv_x", [_exp("keyword_none", True)]),
        _case("case_neg_y", [_exp("keyword_none", True)]),
        # no case_pos_* → capability_rate will be None
    ]
    s = summary.summarize(results)
    assert s.adversarial_rate is not None
    assert s.capability_rate is None
    with pytest.raises(ValueError, match="capability"):
        summary.format_summary_lines(s)


def test_interval_is_widened_by_the_design_effect() -> None:
    """Guard CI widens when cases are repeated (DEFF > 1).

    36 all-pass × k=3 + 1 all-fail × k=3 → 108 passes / 111 records, 37 unique cases.
    At rho≈1.0 (all repetitions agree), DEFF≈3, n_eff≈37.

    Published-but-wrong plain Wilson at n=111: [0.9235, 0.9908].
    Correct design-effect interval at n_eff≈37: [0.8618, 0.9952].

    Pin: EVAL-P17.2 updates these literals when it admits 41 ah_demo_* cases (raising
    the guard battery to 78 cases / ~234 records). Update them in the P17.2 commit —
    never in a later "fix the failing test" commit. That is how a corrected number is
    preserved rather than silently reverted.
    """
    from rate_stats import wilson_interval

    guard_results: list[dict] = []
    for i in range(36):
        for _ in range(3):  # k=3 repetitions of the same case
            guard_results.append(_case(f"case_adv_{i:02d}", [_exp("keyword_none", True)]))
    for _ in range(3):
        guard_results.append(_case("case_neg_failing", [_exp("keyword_none", False)]))

    cap_results = [_case("case_pos_x", [_exp("affirms_judge", True)])]
    results = guard_results + cap_results

    s = summary.summarize(results)

    # Point estimate unchanged: 108/111 = 0.9730…
    assert s.adversarial_passes == 108
    assert s.guard_turns == 111
    assert abs(s.adversarial_rate - 108 / 111) < 1e-6

    # Plain Wilson (published-but-wrong) interval at n=111
    plain_low, plain_high = wilson_interval(108, 111)

    # Design-effect-corrected interval must be strictly wider
    assert s.adversarial_ci_low < plain_low, (
        f"Expected ci_low {s.adversarial_ci_low:.4f} < plain {plain_low:.4f} — "
        "DEFF correction not applied"
    )
    assert s.adversarial_ci_high > plain_high, (
        f"Expected ci_high {s.adversarial_ci_high:.4f} > plain {plain_high:.4f} — "
        "DEFF correction not applied"
    )


def test_rho_zero_interval_equals_plain_wilson() -> None:
    """At rho=0 (MSB=0 → ICC clamped to 0), n_eff = n_records and CI = plain Wilson.

    Build k=2 cases where every case has mean_i = grand_mean (1 pass, 1 fail each).
    This forces SS_between=0, MSB=0, raw ICC<0, clamped to 0, DEFF=1.
    """
    import battery_rates
    from rate_stats import wilson_interval

    # 10 cases, each with exactly 1 pass and 1 fail (k=2)
    results = []
    for i in range(10):
        results.append(_case(f"case_adv_{i:02d}", [_exp("keyword_none", True)]))
        results.append(_case(f"case_adv_{i:02d}", [_exp("keyword_none", False)]))

    br = battery_rates.compute_battery_rate(results)
    assert br is not None
    assert br.rho == 0.0
    assert abs(br.n_eff - br.n_records) < 1e-6

    plain_low, plain_high = wilson_interval(br.passes, br.n_records)
    assert abs(br.ci_low - plain_low) < 1e-9
    assert abs(br.ci_high - plain_high) < 1e-9


def test_infra_failure_is_excluded_from_hallucination_count() -> None:
    """Judge infra failures (inconclusive: True) must not count as lore hallucinations.

    3 judge timeouts across 3 guard cases → 0 hallucinations, 3 inconclusive.
    An inconclusive rate of 100% also marks the run invalid.

    RED anchor for EVAL-P17.3: fails before fix because _tally_failures buckets by
    kind alone (affirms_judge timeout → hallucination) and EvalSummary has no
    inconclusive_failures field.
    """

    def _inconclusive(kind: str) -> dict:
        return {
            "kind": kind,
            "passed": False,
            "skipped": False,
            "inconclusive": True,
            "detail": "judge_infra_failure: timeout",
        }

    results = [
        _case("case_adv_x", [_inconclusive("affirms_judge")]),
        _case("case_adv_y", [_inconclusive("affirms_judge")]),
        _case("case_neg_z", [_inconclusive("tone_judge")]),
    ]
    s = summary.summarize(results)
    assert s.hallucination_failures == 0
    assert s.inconclusive_failures == 3
    assert not s.is_run_valid


def test_capability_battery_counts_deterministic_only_cases(tmp_path) -> None:
    """summarize_from_dir sees all 7 capability cases, not just the 2 with judge rows.

    2 case_pos_* cases have judge rows only (judged.jsonl).
    5 more case_pos_* cases have deterministic rows only (deterministic_judged.jsonl).
    Reading both sources must raise capability_turns from 2 to 7.

    RED anchor: fails with AttributeError (summarize_from_dir not yet defined) or
    AssertionError (capability_turns == 2, not 7) before the fix.
    """
    import json

    judged_rows = [
        {
            "record_id": "case_pos_a:tone_judge:0",
            "case_id": "case_pos_a",
            "judge_kind": "tone_judge",
            "passed": True,
            "score": True,
            "detail": "",
            "judge_model": "m",
            "repetition": 0,
        },
        {
            "record_id": "case_pos_b:tone_judge:0",
            "case_id": "case_pos_b",
            "judge_kind": "tone_judge",
            "passed": True,
            "score": True,
            "detail": "",
            "judge_model": "m",
            "repetition": 0,
        },
    ]
    (tmp_path / "judged.jsonl").write_text(
        "\n".join(json.dumps(r) for r in judged_rows), encoding="utf-8"
    )

    det_rows = [
        {
            "record_id": f"case_pos_{c}:schema:0",
            "repetition": 0,
            "matcher_kind": "schema",
            "passed": True,
            "score": True,
            "reasoning": "ok",
        }
        for c in ["c", "d", "e", "f", "g"]
    ]
    (tmp_path / "deterministic_judged.jsonl").write_text(
        "\n".join(json.dumps(r) for r in det_rows), encoding="utf-8"
    )

    s = summary.summarize_from_dir(tmp_path)
    assert s.capability_turns == 7
