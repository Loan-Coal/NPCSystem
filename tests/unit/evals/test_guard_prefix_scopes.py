"""
Module: test_guard_prefix_scopes
Layer: tests (unit)
Purpose: Pin the deliberate difference between the runner's guard prefixes and the
         publishing tuple (ISSUE-243 / R2.6b). The runner scores only the YAML
         adversarial+negative battery; `ah_demo_` cases are loaded and scored by a
         different runner with different expectations. Aligning the two tuples looks
         like a one-line fix, is a no-op today, and would be actively wrong if the
         runner ever learned to load JSON cases.
Dependencies: pytest; runner, case_stats, summary (evals/)
Used by: `make test`, `make check` via test-cov-evals.

No RED anchor: this commit changes no behaviour. It corrects a comment that named a
symbol which does not exist and encodes the reason the difference is intentional.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import case_stats
import runner
import summary


def test_the_runner_scores_a_narrower_battery_than_the_publishers() -> None:
    """The runner's tuple is a strict subset of the publishing tuple, by design."""
    assert runner._GUARD_PREFIXES == ("case_adv_", "case_neg_")
    assert case_stats._GUARD_PREFIXES == ("case_adv_", "case_neg_", "ah_demo_")
    assert set(runner._GUARD_PREFIXES) < set(case_stats._GUARD_PREFIXES)


def test_summary_declares_no_guard_prefix_tuple() -> None:
    """The corrected reference: runner's comment used to name `summary._GUARD_PREFIXES`.

    That symbol has never existed — the canonical publishing tuple lives in case_stats.
    A future reader following the old comment would have found nothing, or worse, added
    "ah_demo_" to the runner on its authority.
    """
    assert not hasattr(summary, "_GUARD_PREFIXES")


def test_the_runner_loads_only_yaml_so_ah_demo_cases_never_reach_it(tmp_path: Path) -> None:
    """The structural reason aligning the tuples would be a no-op.

    `ah_demo_` cases ship as JSON. The runner globs *.yaml, so they are invisible to it
    however the guard tuple is spelled.
    """
    (tmp_path / "anti_hallucination_demo.json").write_text(
        json.dumps([{"case_id": "ah_demo_sorn_war_known"}]), encoding="utf-8"
    )
    assert runner._load_cases(tmp_path) == []


def test_ah_demo_cases_are_json_not_yaml() -> None:
    """The shipped fixture really is the JSON file this reasoning assumes."""
    repo_root = Path(__file__).resolve().parents[3]
    fixture = repo_root / "evals" / "cases" / "anti_hallucination_demo.json"
    assert fixture.is_file()
    ids = [c.get("id") or c.get("case_id") for c in json.loads(fixture.read_text(encoding="utf-8"))]
    assert any(str(i).startswith("ah_demo_") for i in ids)
    assert not list((repo_root / "evals" / "cases").glob("ah_demo_*.yaml"))


def test_guard_expectations_are_authored_for_the_yaml_battery() -> None:
    """What the runner injects, and why it must not reach a refusal-graded case.

    A correct refusal is short; `min_length` would score it as a guard failure.
    """
    kinds = {e["kind"] for e in runner._guard_expectations(None)}
    assert "min_length" in kinds
    assert kinds & {"tone_judge", "keyword_none"}


# ---------------------------------------------------------------------------
# R2.5 / DEC-243: the two guard populations are named and never re-combined
# ---------------------------------------------------------------------------


def test_the_two_guard_populations_are_named_separately() -> None:
    """DEC-243: adversarial and anti-hallucination are graded by different contracts.

    `case_adv_`/`case_neg_` carry the YAML battery's tone_judge / affirms_judge / schema /
    keyword_none / min_length. `ah_demo_` carries refusal_judge and
    anti_hallucination_grounded instead. Two grading contracts, not one with a gap — so a
    single tuple spanning both is what let one published rate mean two things.
    """
    assert case_stats._ADVERSARIAL_PREFIXES == ("case_adv_", "case_neg_")
    assert case_stats._ANTI_HALLUCINATION_PREFIXES == ("ah_demo_",)
    assert not set(case_stats._ADVERSARIAL_PREFIXES) & set(case_stats._ANTI_HALLUCINATION_PREFIXES)


def test_the_runner_battery_is_exactly_the_adversarial_population() -> None:
    """Under the split the runner's tuple stops being a subset that looks like a bug.

    It was flagged as one (ISSUE-243's title) because it did not mirror the publishing
    tuple. It now IS the adversarial population's definition, and equality pins that.
    """
    assert runner._GUARD_PREFIXES == case_stats._ADVERSARIAL_PREFIXES


def test_every_guard_case_belongs_to_exactly_one_population() -> None:
    """A case counted in both, or in neither, would silently distort both rates."""
    for case_id in ("case_adv_x", "case_neg_x", "ah_demo_x"):
        assert case_stats.classify_battery(case_id) == "guard"
        assert case_stats.guard_population(case_id) in ("adversarial", "anti_hallucination")

    assert case_stats.guard_population("case_adv_x") == "adversarial"
    assert case_stats.guard_population("ah_demo_x") == "anti_hallucination"


def test_a_non_guard_case_has_no_guard_population() -> None:
    """Capability cases must not be silently absorbed into either guard rate."""
    import pytest

    with pytest.raises(ValueError):
        case_stats.guard_population("case_pos_x")


def test_no_combined_guard_rate_can_be_emitted() -> None:
    """DEC-243's core invariant, asserted against the model rather than the call sites.

    Removing the markdown row would leave the fields in place for the next caller to
    reach for. The rate fields themselves are gone, so a combined figure cannot be
    produced without deliberately re-adding them.

    Counts are exempt on purpose: `check_conservation` needs
    `guard_cases + capability_cases == total_cases`, and a count over two populations is
    a count, not an average of two different grading contracts.
    """
    fields = {f.name for f in dataclasses.fields(summary.EvalSummary)}

    assert not {"guard_rate", "guard_ci_low", "guard_ci_high", "guard_passes"} & fields
    assert {"adversarial_rate", "anti_hallucination_rate"} <= fields
    assert {"guard_cases", "guard_turns"} <= fields, "counts stay: conservation needs them"


def test_the_published_markdown_names_both_populations_and_no_union() -> None:
    """The rendered table must not carry a row spanning both expectation sets."""
    results = (
        [_adv_case(f"case_adv_{i}", passed=True) for i in range(3)]
        + [_adv_case(f"ah_demo_{i}", passed=False) for i in range(2)]
        + [_adv_case(f"case_pos_{i}", passed=True) for i in range(2)]
    )

    rendered = "\n".join(summary.format_summary_markdown(summary.summarize(results)))

    assert "Guard - adversarial" in rendered
    assert "Guard - anti-hallucination" in rendered
    assert "adv + neg + ah_demo_*" not in rendered, "the union row is what DEC-243 retires"


def _adv_case(case_id: str, *, passed: bool) -> dict:
    """One result dict with a single non-skipped expectation."""
    return {
        "case_id": case_id,
        "passed": passed,
        "expectations": [{"kind": "keyword_none", "passed": passed, "skipped": False}],
    }
