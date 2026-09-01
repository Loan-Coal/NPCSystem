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
