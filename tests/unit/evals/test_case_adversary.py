"""
Module: tests.unit.evals.test_case_adversary
Layer: tests
Purpose: Unit tests for evals/case_adversary.py — EVAL-P26.1's adversarial CASE
         reviewer. Splits into deterministic checks (pure Python, no LLM, the majority
         of the value) and judgment checks emitted as a batch for the existing
         Opus batch/paste workflow.
Dependencies: json, pathlib, sys, pytest, yaml, case_adversary
Used by: make test / make check (pytest discovery)

No network I/O: the LLM judge is stubbed, exactly as
tests/unit/evals/test_capability_echo_resistance.py stubs it, so a judge-decided
expectation cannot make this module flake or silently read as clean.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import matchers  # noqa: E402
from case_adversary import (  # noqa: E402
    ADVERSARY_PROMPT_PATH,
    GROUNDED_EDGE_TYPES,
    RETIRED_EDGE_ALIASES,
    CheckName,
    JudgmentFinding,
    MalformedFindingsError,
    Severity,
    build_review_batch,
    load_adversary_prompt,
    parse_findings,
    render_batch,
    review_case,
)
from matchers import JudgeResult  # noqa: E402


@pytest.fixture(autouse=True)
def _no_live_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the LLM judge; this module must do no network I/O."""
    monkeypatch.setattr(
        matchers,
        "_run_binary_judge",
        lambda *args, **kwargs: JudgeResult(score=None, error="unit_test_no_judge"),
    )


def _case(**overrides: object) -> dict:
    """A clean capability case that passes every deterministic check."""
    case = {
        "case_id": "case_pos_captain_sorn_gate_muster",
        "description": "sorn should surface the muster he was ordered to run.",
        "seed": {"npc_id": "captain_sorn", "player_id": "player_eval", "requires_world": "demo"},
        "input": {"player_message": "Captain, is anything different about the watch this week?"},
        "expected": [
            {"kind": "schema"},
            {"kind": "keyword_any", "keywords": ["muster", "king's pass", "armies", "border"]},
        ],
        "notes": "Grounding: KNOWS_ABOUT(captain_sorn, northern_war_begins).",
    }
    case.update(overrides)  # type: ignore[arg-type]
    return case


def _checks(review: object) -> set[CheckName]:
    """The set of check names a review flagged."""
    return {f.check for f in review.findings}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# RED anchor — the exact defect the EVAL-P20.2 audit found
# ---------------------------------------------------------------------------


def test_keyword_tokens_lifted_from_the_players_own_message_are_flagged() -> None:
    """The audit's finding: one canned hedge passed 6 of 7 capability cases because the
    keyword_any list was drawn from the vocabulary the case itself supplied.

    `case_pos_aldric_trade_disruption` asks about war and trade, then scores on 'war'
    and 'trade'. That case measures parroting, not knowledge.
    """
    case = _case(
        input={"player_message": "The war in the north has hurt trade, has it not?"},
        expected=[
            {"kind": "schema"},
            {"kind": "keyword_any", "keywords": ["war", "trade", "caravan"]},
        ],
    )

    review = review_case(case)
    finding = next(f for f in review.findings if f.check is CheckName.PROMPT_SUPPLIED_TOKENS)

    assert finding.severity is Severity.BLOCKER
    assert "war" in finding.detail and "trade" in finding.detail
    assert "caravan" not in finding.detail


def test_a_case_scoring_on_grounded_fact_tokens_is_not_flagged() -> None:
    """The rule that satisfies the contract: draw tokens from the fact, not the prompt."""
    review = review_case(_case())

    assert CheckName.PROMPT_SUPPLIED_TOKENS not in _checks(review)


# ---------------------------------------------------------------------------
# Gameability — reusing hedge_responder_probe and the echo machinery
# ---------------------------------------------------------------------------


def test_a_case_beaten_by_an_echo_of_its_own_prompt_is_flagged() -> None:
    """A response that only reflects the question back demonstrates nothing."""
    case = _case(
        input={"player_message": "Is the muster at the border already under way, Captain?"},
        expected=[{"kind": "schema"}, {"kind": "keyword_any", "keywords": ["muster", "border"]}],
    )

    assert CheckName.BEATEN_BY_ECHO in _checks(review_case(case))


def test_a_case_beaten_by_the_reference_hedge_is_flagged() -> None:
    """The canned always-hedge responder asserts no fact; it must score no capability."""
    case = _case(
        expected=[{"kind": "schema"}, {"kind": "keyword_any", "keywords": ["war", "harvest"]}],
    )

    assert CheckName.BEATEN_BY_HEDGE in _checks(review_case(case))


def test_a_resistant_case_is_beaten_by_neither() -> None:
    """The clean case must survive both adversaries."""
    checks = _checks(review_case(_case()))

    assert CheckName.BEATEN_BY_ECHO not in checks
    assert CheckName.BEATEN_BY_HEDGE not in checks


def test_a_judge_decided_case_is_reported_unmeasured_never_clean() -> None:
    """Offline, a tone_judge expectation is UNMEASURED — it must not read as resistant.

    Same treatment as test_capability_echo_resistance's exclusion: a check that could
    not run is a reported hole, not a silent pass.
    """
    case = _case(
        expected=[{"kind": "schema"}, {"kind": "tone_judge", "description": "engages as a soldier"}],
    )
    review = review_case(case)

    assert CheckName.JUDGE_DECIDED_UNMEASURED in _checks(review)


# ---------------------------------------------------------------------------
# Grounding — the declared edge type must be one the registry actually has
# ---------------------------------------------------------------------------


def test_a_retired_edge_alias_is_flagged_by_name() -> None:
    """HAS_MEMORY / HAS_GOAL / HAS_SECRET do not exist; the registry says REMEMBERS /
    PURSUES / KNOWS_SECRET. ISSUE-148 — evals/case_drafts.py still carries the wrong
    three and returns HTTP 422 for them."""
    review = review_case(_case(notes="Grounding: HAS_GOAL(captain_sorn, goal_captain_sorn_0)."))
    finding = next(f for f in review.findings if f.check is CheckName.UNDECLARED_GROUNDING_EDGE)

    assert "HAS_GOAL" in finding.detail
    assert "PURSUES" in finding.detail
    assert RETIRED_EDGE_ALIASES["HAS_GOAL"] == "PURSUES"


def test_notes_naming_no_edge_type_at_all_are_flagged() -> None:
    """A case that cannot be traced to a graph edge cannot be verified against one."""
    review = review_case(_case(notes="Requires demo world seed."))

    assert CheckName.UNDECLARED_GROUNDING_EDGE in _checks(review)


def test_every_real_edge_type_is_accepted() -> None:
    """The five types CAPABILITY_CASES.md names, read through the typed admin endpoints."""
    assert GROUNDED_EDGE_TYPES == frozenset(
        {"KNOWS_ABOUT", "BELIEVES", "REMEMBERS", "PURSUES", "KNOWS_SECRET"}
    )
    for edge in GROUNDED_EDGE_TYPES:
        review = review_case(_case(notes=f"Grounding: {edge}(captain_sorn, node_x)."))
        assert CheckName.UNDECLARED_GROUNDING_EDGE not in _checks(review)


def test_the_reviewer_never_asserts_the_fact_exists_in_the_graph() -> None:
    """Scope boundary: this module is pure and offline, so it checks that the DECLARED
    edge type is real, never that the NPC actually holds the node. Confirming the node
    needs GET /v1/admin/{beliefs,goals,memories,secrets}/{npc_id} — a live step, named
    in the review so it is not mistaken for done."""
    review = review_case(_case())

    assert review.live_verification_required
    assert "/v1/admin/" in review.live_verification_hint


# ---------------------------------------------------------------------------
# The batch/paste side — mirrors evals/calibration/oracle_batches/
# ---------------------------------------------------------------------------


def test_the_batch_carries_what_a_judgment_check_needs_and_nothing_else() -> None:
    """Leading-prompt / self-answering / insider-vocabulary are judgment calls; they go
    to Opus through the existing batch/paste workflow, not through a new API client."""
    items = build_review_batch([_case()])

    assert len(items) == 1
    item = items[0]
    assert item.case_id == "case_pos_captain_sorn_gate_muster"
    assert item.player_message.startswith("Captain, is anything different")
    assert "keyword_any" in item.expectation_summary


def test_the_rendered_batch_is_a_json_array_like_the_oracle_batches() -> None:
    """Same on-disk shape as evals/calibration/oracle_batches/batch_001.json."""
    parsed = json.loads(render_batch(build_review_batch([_case()])))

    assert isinstance(parsed, list)
    assert parsed[0]["case_id"] == "case_pos_captain_sorn_gate_muster"


def test_the_prompt_lives_in_prompts_eval_not_in_python() -> None:
    """CLAUDE.md: nothing passed to an LLM may be a string literal in Python."""
    assert ADVERSARY_PROMPT_PATH.exists()
    doc = yaml.safe_load(ADVERSARY_PROMPT_PATH.read_text(encoding="utf-8"))

    assert set(doc) >= {"template", "checks"}
    assert load_adversary_prompt() == doc["template"]


def test_imported_findings_are_validated_not_trusted() -> None:
    """The pasted result is an external input, so it is parsed through a Pydantic model."""
    lines = "\n".join(
        [
            json.dumps(
                {
                    "case_id": "case_pos_x",
                    "check": "leading_prompt",
                    "severity": "blocker",
                    "detail": "the message states the answer.",
                }
            ),
            "",
        ]
    )
    findings = parse_findings(lines)

    assert findings == (
        JudgmentFinding(
            case_id="case_pos_x",
            check="leading_prompt",
            severity=Severity.BLOCKER,
            detail="the message states the answer.",
        ),
    )


def test_a_malformed_imported_line_raises_rather_than_being_dropped() -> None:
    """Never silently drop a finding: a batch that half-imports is worse than none."""
    with pytest.raises(MalformedFindingsError):
        parse_findings('{"case_id": "case_pos_x", "check": "leading_prompt"}')

    with pytest.raises(MalformedFindingsError):
        parse_findings("not json at all")


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


def test_the_module_docstring_states_the_case_versus_response_boundary() -> None:
    """EVAL-P26.1 reviews CASES. EVAL-P28.1 labels RESPONSES. Conflating them is how the
    reference side stays single-rater."""
    import case_adversary

    doc = case_adversary.__doc__ or ""

    assert "EVAL-P28.1" in doc
    assert "RESPONSES" in doc and "CASES" in doc
