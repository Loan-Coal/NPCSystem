"""
Module: test_judge_panel
Layer: test (unit)
Purpose: Tests for evals/judge_panel.py — multi-judge execution and persistence
         (EVAL-P21.1) and the 2-of-3 consensus rule + inter-judge agreement
         (EVAL-P21.2). Fixture-tested with an injected judge_fn (no live
         Ollama needed) and against the real committed k3_73e6c36 artifact
         where noted, per the roadmap's own "doesn't need the new regen
         artifact" scoping.

SCAFFOLDING STATUS: this code is real and tested, but HUMAN GATE H7 stays
closed until EVAL-P20.4 (regeneration #1) actually runs — see ROADMAP.md's
EVAL-P21.1/P21.2 Notes. These tests pin the mechanism against injected/
fixture verdicts, not a live 3-model Ollama panel run.
Dependencies: pytest, judge_panel, matchers (JudgeResult) (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

from matchers import JudgeResult
from judge_panel import (
    consensus_verdict,
    pairwise_agreement,
    run_panel,
    to_judged_rows,
)

_PANEL = ("mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b")


def _stub_judge_fn(verdict_by_model: dict[str, bool | None]):
    """Build an injectable judge_fn returning a fixed verdict per model."""

    def _fn(model: str, criteria: str, content: str) -> JudgeResult:
        score = verdict_by_model[model]
        return JudgeResult(score=score, error="" if score or score is None else "no")

    return _fn


# ---------------------------------------------------------------------------
# RED anchor — EVAL-P21.1
# ---------------------------------------------------------------------------


def test_panel_persists_one_verdict_row_per_judge_per_record() -> None:
    """A record judged by 3 models yields 3 rows, each carrying judge_model."""
    judge_fn = _stub_judge_fn({m: True for m in _PANEL})
    verdicts = run_panel(
        "case_adv_x:tone_judge:0#r0", "be gruff", "some response",
        models=_PANEL, judge_fn=judge_fn,
    )
    rows = to_judged_rows(verdicts)

    assert len(rows) == 3
    judge_models = {r["judge_model"] for r in rows}
    assert judge_models == set(_PANEL)
    assert all(r["record_id"] == "case_adv_x:tone_judge:0#r0" for r in rows)


def test_panel_errors_yield_explicit_inconclusive_never_silent_pass() -> None:
    """A judge that errors produces score=None and passed=False, never a silent pass."""
    judge_fn = _stub_judge_fn({"mixtral:8x7b": True, "qwen2.5:14b": None, "llama3.1:8b": False})
    verdicts = run_panel(
        "case_adv_x:tone_judge:0#r0", "be gruff", "some response",
        models=_PANEL, judge_fn=judge_fn,
    )
    rows = to_judged_rows(verdicts)
    inconclusive_row = next(r for r in rows if r["judge_model"] == "qwen2.5:14b")
    assert inconclusive_row["score"] is None
    assert inconclusive_row["passed"] is False  # never a silent pass
    assert inconclusive_row["inconclusive"] is True


# ---------------------------------------------------------------------------
# RED anchor — EVAL-P21.2
# ---------------------------------------------------------------------------


def test_single_dissenting_judge_does_not_create_a_hallucination() -> None:
    """The named audit false positive: 1 of 3 judges fails it — must be outvoted.

    Real case (EVAL-P21.2's own validation text): case_neg_injection_001 —
    mixtral alone said FAIL (score=True, hallucination), the other two judges
    said PASS (score=False). Under 2-of-3 consensus this must NOT count as a
    hallucination.
    """
    votes = [True, False, False]  # mixtral=fail, qwen2.5:14b=pass, llama3.1:8b=pass
    consensus, n_available = consensus_verdict(votes)
    assert consensus is False
    assert n_available == 3


def test_two_of_three_agreeing_confirms_hallucination() -> None:
    """2 of 3 judges failing the record IS enough to confirm a hallucination."""
    votes = [True, True, False]
    consensus, n_available = consensus_verdict(votes)
    assert consensus is True
    assert n_available == 3


def test_inconclusive_votes_do_not_count_toward_consensus() -> None:
    """A None (infra-failure) vote can never itself push consensus toward True."""
    votes = [True, None, None]
    consensus, n_available = consensus_verdict(votes)
    assert consensus is False  # only 1 real failure vote, not enough
    assert n_available == 1


def test_pairwise_agreement_all_agree_is_one() -> None:
    """Three records where all 3 judges agree every time → agreement rate 1.0."""
    records = [
        [True, True, True],
        [False, False, False],
    ]
    result = pairwise_agreement(records)
    assert result.rate == 1.0
    assert result.ci_low is not None and result.ci_high is not None


def test_pairwise_agreement_partial_disagreement() -> None:
    """One dissenting judge out of 3 pairs per record lowers the agreement rate below 1.0."""
    records = [
        [True, False, False],  # 1 of 3 pairs agree: (q,l) agree; (m,q) and (m,l) disagree
    ]
    result = pairwise_agreement(records)
    assert 0.0 < result.rate < 1.0


def test_pairwise_agreement_ignores_inconclusive_votes() -> None:
    """A record with fewer than 2 real votes contributes no pairs."""
    records = [
        [True, None, None],  # only 1 real vote — no pair possible
        [True, True, True],  # 3 pairs, all agree
    ]
    result = pairwise_agreement(records)
    assert result.rate == 1.0  # only the second record's pairs count


# ---------------------------------------------------------------------------
# Fixture test against real k3_73e6c36 data — doesn't need the new regen artifact
# ---------------------------------------------------------------------------


def test_panel_runs_against_a_real_k3_case_with_stubbed_verdicts() -> None:
    """Panel mechanism runs against a real k3_73e6c36 case's criteria/output_text.

    Uses the real content (not synthetic strings) with stubbed judge verdicts,
    per the session's "fixture-tested against k3_73e6c36" instruction — this
    proves the mechanism works against real case data without requiring a
    live 3-model Ollama panel run (which needs EVAL-P20.4's post-regen
    artifact and H7 open).
    """
    import json
    from pathlib import Path

    k3_outputs = (
        Path(__file__).resolve().parents[3]
        / "evals" / "generations" / "k3_73e6c36" / "outputs.jsonl"
    )
    rows = [json.loads(line) for line in k3_outputs.read_text(encoding="utf-8").splitlines() if line.strip()]
    real_row = next(r for r in rows if r.get("criteria"))

    judge_fn = _stub_judge_fn({"mixtral:8x7b": True, "qwen2.5:14b": False, "llama3.1:8b": False})
    verdicts = run_panel(
        real_row["record_id"], real_row["criteria"], real_row["npc_response"],
        models=_PANEL, judge_fn=judge_fn,
    )
    assert len(verdicts) == 3
    votes = [v.score for v in verdicts]
    consensus, _ = consensus_verdict(votes)
    assert consensus is False  # 1 of 3 — outvoted


# ---------------------------------------------------------------------------
# summary.py integration (EVAL-P21.2)
# ---------------------------------------------------------------------------


def test_summary_includes_inter_judge_agreement() -> None:
    """format_summary_lines renders inter-judge agreement when supplied."""
    import summary  # noqa: PLC0415  (evals/ path — deferred import, matches sibling tests)

    guard_case = {
        "case_id": "case_adv_x",
        "description": "",
        "passed": True,
        "expectations": [{"kind": "keyword_none", "passed": True, "skipped": False, "detail": ""}],
        "response": {"npc_response": "x"},
        "error": None,
    }
    cap_case = {
        "case_id": "case_pos_x",
        "description": "",
        "passed": True,
        "expectations": [{"kind": "affirms_judge", "passed": True, "skipped": False, "detail": ""}],
        "response": {"npc_response": "y"},
        "error": None,
    }
    s = summary.summarize([guard_case, cap_case])
    agreement = pairwise_agreement([[True, True, False], [False, False, False]])

    lines = summary.format_summary_lines(s, panel_agreement=agreement)
    blob = "\n".join(lines)

    assert "inter-judge agreement" in blob.lower()
    assert f"{agreement.agreeing_pairs}/{agreement.total_pairs}" in blob
