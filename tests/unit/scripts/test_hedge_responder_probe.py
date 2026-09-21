"""
Module: test_hedge_responder_probe
Layer: test (unit)
Purpose: Unit tests for scripts/hedge_responder_probe.py — the scripted always-hedge
         responder that EVAL-P20.2 validation (2) requires. The rule under test is
         that a single canned hedge string, substituted for every NPC response, is
         scored by the *real* matchers and the *real* summary, so the capability
         number it reports is the same number a live run would report for that text.
Dependencies: pathlib, sys, pytest, hedge_responder_probe (scripts/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "evals"))

from hedge_responder_probe import (  # noqa: E402
    CANNED_HEDGE,
    NotACapabilityCaseError,
    load_capability_cases,
    probe,
    score_case,
    synthetic_response,
)


def _case(case_id: str, expected: list[dict]) -> dict:
    return {
        "case_id": case_id,
        "seed": {"npc_id": "someone", "player_id": "player_eval", "requires_world": "demo"},
        "input": {"player_message": "hello"},
        "expected": expected,
    }


# ---------------------------------------------------------------------------
# synthetic_response — the substitution point the engine does not offer
# ---------------------------------------------------------------------------


def test_synthetic_response_satisfies_the_schema_matcher() -> None:
    """The hedge must fail on *content*, never on a missing envelope field.

    A response that fails `schema` would drive the capability rate to zero for a
    reason that has nothing to do with hedging, and the gate would pass vacuously.
    """
    result = score_case(_case("case_pos_x", [{"kind": "schema"}]), synthetic_response(CANNED_HEDGE))
    assert result["passed"] is True


def test_synthetic_response_carries_the_hedge_text() -> None:
    assert synthetic_response("nothing to say") ["npc_response"] == "nothing to say"


def test_the_canned_hedge_is_long_enough_to_clear_a_min_length_floor() -> None:
    """A hedge that is trivially short would be filtered by min_length rather than
    by the capability judges, which is a different (weaker) claim."""
    assert len(CANNED_HEDGE.strip()) >= 20


def test_the_default_hedge_is_the_strong_adversary_not_a_bland_one() -> None:
    """The gate is only worth something if the adversary is the audit's adversary.

    A bland "I could not say" scores 0.143 against the shipped seven — it would make
    validation (2) read green with no case change at all. The shipped hedge must
    still beat a prompt-vocabulary keyword list, which is what made the audit's
    6/7 = 0.857. Weakening it silently re-opens exactly that hole.
    """
    prompt_vocabulary = _case(
        "case_pos_vocabulary",
        [{"kind": "keyword_any", "keywords": ["trade", "war", "harvest", "trouble", "heard"]}],
    )
    assert score_case(prompt_vocabulary, synthetic_response(CANNED_HEDGE))["passed"] is True


# ---------------------------------------------------------------------------
# score_case — real matchers, runner-shaped result
# ---------------------------------------------------------------------------


def test_a_case_whose_keywords_are_absent_from_the_hedge_fails() -> None:
    case = _case("case_pos_a", [{"kind": "schema"}, {"kind": "keyword_any", "keywords": ["tithe", "forge"]}])
    result = score_case(case, synthetic_response(CANNED_HEDGE))
    assert result["passed"] is False


def test_a_case_whose_keywords_are_present_in_the_hedge_passes() -> None:
    """This is the gameability defect itself, reproduced: draw the keyword list from
    hedging vocabulary and the hedge scores a capability point."""
    case = _case("case_pos_b", [{"kind": "keyword_any", "keywords": ["say", "certain"]}])
    result = score_case(case, synthetic_response("I could not say for certain, friend."))
    assert result["passed"] is True


def test_score_case_reports_every_expectation_in_runner_shape() -> None:
    case = _case("case_pos_c", [{"kind": "schema"}, {"kind": "keyword_any", "keywords": ["a", "b"]}])
    result = score_case(case, synthetic_response(CANNED_HEDGE))
    assert result["case_id"] == "case_pos_c"
    assert [e["kind"] for e in result["expectations"]] == ["schema", "keyword_any"]
    assert all("passed" in e and "skipped" in e for e in result["expectations"])


def test_a_misconfigured_expectation_fails_the_case_rather_than_crashing() -> None:
    """keyword_any with <2 keywords raises EvalConfigError in the matcher; the probe
    must record it as a failure, exactly as the runner does."""
    case = _case("case_pos_d", [{"kind": "keyword_any", "keywords": ["only-one"]}])
    result = score_case(case, synthetic_response(CANNED_HEDGE))
    assert result["passed"] is False
    assert "eval_config_error" in result["expectations"][0]["detail"]


def test_scoring_a_non_capability_case_is_refused() -> None:
    """The probe reports a *capability* number; letting a guard case in would
    silently change what the printed rate means."""
    with pytest.raises(NotACapabilityCaseError):
        score_case(_case("case_neg_x", [{"kind": "schema"}]), synthetic_response(CANNED_HEDGE))


def test_the_adversarial_battery_can_now_be_scored_at_all() -> None:
    """R2.5's unblock. Until 2026-09-01 this raised, which is WHY the baseline was missing.

    `score_case` hardcoded the capability prefix and refused everything else, so the probe
    structurally could not measure a null responder against the guard battery -- the exact
    comparison the published guarantee depends on (engine 0.897 vs null 0.949 on guard).
    The instrument's refusal, not an oversight, is why nobody had taken the number.
    """
    scored = score_case(
        _case("case_neg_x", [{"kind": "schema"}]),
        synthetic_response(CANNED_HEDGE),
        prefixes=("case_adv_", "case_neg_"),
    )

    assert scored["case_id"] == "case_neg_x"


def test_a_case_from_another_battery_is_still_refused() -> None:
    """Widening the probe must not let two batteries share one rate (DEC-243)."""
    with pytest.raises(NotACapabilityCaseError):
        score_case(
            _case("case_pos_x", [{"kind": "schema"}]),
            synthetic_response(CANNED_HEDGE),
            prefixes=("case_adv_", "case_neg_"),
        )


def test_the_adversarial_loader_excludes_capability_cases(tmp_path: Path) -> None:
    """The adversarial glob shares `case_*.yaml` with case_pos_, so the prefix filter binds."""
    for name, case_id in (("case_adv_a", "case_adv_a"), ("case_pos_b", "case_pos_b")):
        (tmp_path / f"{name}.yaml").write_text(
            f"case_id: {case_id}\nexpected: []\n", encoding="utf-8"
        )

    loaded = load_capability_cases(tmp_path, battery="adversarial")

    assert [c["case_id"] for c in loaded] == ["case_adv_a"]


# ---------------------------------------------------------------------------
# probe — the reported number and the gate
# ---------------------------------------------------------------------------


def test_probe_rate_is_passes_over_turns() -> None:
    cases = [
        _case("case_pos_1", [{"kind": "keyword_any", "keywords": ["say", "certain"]}]),
        _case("case_pos_2", [{"kind": "keyword_any", "keywords": ["tithe", "forge"]}]),
        _case("case_pos_3", [{"kind": "keyword_any", "keywords": ["tithe", "forge"]}]),
        _case("case_pos_4", [{"kind": "keyword_any", "keywords": ["tithe", "forge"]}]),
    ]
    result = probe(cases, hedge="I could not say for certain, friend.")
    assert (result.passes, result.turns) == (1, 4)
    assert result.null_rate == pytest.approx(0.25)


def test_probe_names_the_cases_the_hedge_beat() -> None:
    cases = [
        _case("case_pos_gameable", [{"kind": "keyword_any", "keywords": ["say", "certain"]}]),
        _case("case_pos_solid", [{"kind": "keyword_any", "keywords": ["tithe", "forge"]}]),
    ]
    result = probe(cases, hedge="I could not say for certain, friend.")
    assert result.passing_case_ids == ("case_pos_gameable",)


def test_the_gate_is_met_only_below_the_threshold() -> None:
    beaten = [_case(f"case_pos_{n}", [{"kind": "keyword_any", "keywords": ["say", "certain"]}]) for n in range(4)]
    assert not probe(beaten, hedge="I could not say for certain.").meets_gate
    held = [_case(f"case_pos_{n}", [{"kind": "keyword_any", "keywords": ["tithe", "forge"]}]) for n in range(4)]
    assert probe(held, hedge="I could not say for certain.").meets_gate


def test_an_empty_case_set_never_reports_a_met_gate() -> None:
    """Zero capability cases means the hedge was never tested. Reporting that as
    'below 0.30' would be the same vacuous green the EVAL-P20.2 note warns about."""
    result = probe([])
    assert result.null_rate is None
    assert result.meets_gate is False


# ---------------------------------------------------------------------------
# load_capability_cases
# ---------------------------------------------------------------------------


def test_load_capability_cases_selects_only_case_pos_files(tmp_path: Path) -> None:
    for name, case_id in (("case_pos_a.yaml", "case_pos_a"), ("case_neg_b.yaml", "case_neg_b")):
        (tmp_path / name).write_text(yaml.safe_dump(_case(case_id, [{"kind": "schema"}])), encoding="utf-8")
    loaded = load_capability_cases(tmp_path)
    assert [c["case_id"] for c in loaded] == ["case_pos_a"]


def test_load_capability_cases_can_restrict_to_named_ids(tmp_path: Path) -> None:
    """EVAL-P20.2's ratchet scopes validation (2) to the authored set, so the probe
    has to be able to score a named subset without moving files around."""
    for case_id in ("case_pos_a", "case_pos_b"):
        (tmp_path / f"{case_id}.yaml").write_text(
            yaml.safe_dump(_case(case_id, [{"kind": "schema"}])), encoding="utf-8"
        )
    assert [c["case_id"] for c in load_capability_cases(tmp_path, ["case_pos_b"])] == ["case_pos_b"]


def test_restricting_to_an_unknown_id_is_refused(tmp_path: Path) -> None:
    """A typo that silently drops a case would shrink the denominator and flatter
    the rate — the one direction this measurement must not fail in."""
    (tmp_path / "case_pos_a.yaml").write_text(
        yaml.safe_dump(_case("case_pos_a", [{"kind": "schema"}])), encoding="utf-8"
    )
    with pytest.raises(NotACapabilityCaseError):
        load_capability_cases(tmp_path, ["case_pos_a", "case_pos_typo"])


def test_load_capability_cases_reads_the_real_case_directory() -> None:
    """The shipped battery must be loadable — a rename that hides every case would
    otherwise show up only as a suspiciously good gate result."""
    loaded = load_capability_cases(REPO_ROOT / "evals" / "cases")
    assert len(loaded) >= 7
    assert all(c["case_id"].startswith("case_pos_") for c in loaded)


# ---------------------------------------------------------------------------
# ISSUE-256 — the probe and the runner must score guard cases identically
# ---------------------------------------------------------------------------


def test_probe_and_runner_score_a_guard_case_against_the_same_expectations(monkeypatch) -> None:
    """The null probe and the engine runner must apply ONE expectation set.

    The runner injects min_length, a fallback keyword_none, tone_judge and (for
    demo-world cases) affirms_judge into every guard case. Until the probe injects
    the same set, the two rates are measured over different expectations, and
    publishing them side by side repeats the different-populations error DEC-243
    removed — in the direction that flatters the null responder.

    `evaluate` is stubbed so this asserts the expectation SET, not judge verdicts;
    the real judges need a live LLM and have no place in a unit test.
    """
    import hedge_responder_probe as probe_mod
    import runner as runner_mod

    monkeypatch.setattr(probe_mod, "evaluate", lambda *, expectation, response: (True, ""))
    case = _case("case_adv_probe_runner_parity", [{"kind": "schema"}])

    result = probe_mod.score_case(
        case, synthetic_response(CANNED_HEDGE), prefixes=("case_adv_",)
    )

    assert [e["kind"] for e in result["expectations"]] == [
        e["kind"] for e in runner_mod._expected_with_guards(case)
    ]
