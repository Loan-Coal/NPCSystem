"""
Module: test_capability_echo_resistance
Layer: test (unit)
Purpose: Ratchet the gameability of the capability battery (EVAL-P20.2). A capability
         case must not be satisfiable by a response that carries no knowledge — neither
         an echo of the case's own player_message nor a canned hedge. The audit found a
         single hedge string passing 6 of 7 capability cases, because `keyword_any` lists
         were drawn from the same vocabulary as the prompt.
Dependencies: pytest, yaml, pathlib, sys, hedge_responder_probe (scripts/)
Used by: pytest (make test / make check)

Why a baseline rather than a flat assertion. All seven shipped cases are gameable and
repairing them changes what they measure, which makes prior generations incomparable —
that is EVAL-P20.1's call, not this module's. They are named in GAMEABLE_BASELINE so the
rule binds every case authored from now on while the known-bad set stays visible and
countable. Same shape as UNCOVERED_BASELINE in test_capability_coverage (DEC-161).
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
    score_case,
    synthetic_response,
)

CASES_DIR = REPO_ROOT / "evals" / "cases"

# Capability cases that a knowledge-free response already beats, recorded 2026-08-10.
#
# RATCHET DOWN when a case is repaired: delete it from this set in the same commit that
# tightens its expectations. `test_gameable_baseline_has_no_stale_entries` fails if you
# forget. Never add to it — a new case that needs an entry here is a case that does not
# test capability, and must be rewritten instead.
GAMEABLE_BASELINE: frozenset[str] = frozenset(
    {
        # Beaten by the canned hedge (and, except for sorn, by their own prompt too):
        # keyword_any lists drawn from the player message's own vocabulary.
        "case_pos_aldric_trade_disruption",
        "case_pos_captain_sorn_war_knowledge",
        "case_pos_mira_gossip_hedging",
        "case_pos_mira_war_gossip_tokens",
        "case_pos_old_henryk_war_rumor_tokens",
        "case_pos_world_blight_guard",
        # Beaten by the echo only: its tone_judge asks whether the speaker engages with
        # the player's illicit request, and the player's own request trivially does.
        "case_pos_lira_fence_trade",
    }
)


def _capability_cases() -> list[dict]:
    """Load every shipped case_pos_* document."""
    return [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(CASES_DIR.glob("case_pos_*.yaml"))
    ]


def _beaten_by(response_text_for: object) -> list[str]:
    """Case ids passed by a knowledge-free response, ignoring the baselined ones."""
    beaten: list[str] = []
    for case in _capability_cases():
        case_id = case["case_id"]
        if case_id in GAMEABLE_BASELINE:
            continue
        text = response_text_for(case)  # type: ignore[operator]
        if score_case(case, synthetic_response(text))["passed"]:
            beaten.append(case_id)
    return sorted(beaten)


def test_no_capability_case_is_beaten_by_an_echo_of_its_own_prompt() -> None:
    """A response that only reflects the question back demonstrates nothing.

    Red means a keyword list was drawn from the player message: pick tokens from the
    grounded fact instead, or the case measures parroting rather than knowledge.
    """
    beaten = _beaten_by(lambda case: case["input"]["player_message"])
    assert not beaten, (
        "these capability cases pass on an echo of their own player_message: "
        + ", ".join(beaten)
        + " — draw the keyword_any tokens from the grounded fact, not from the prompt."
    )


def test_no_capability_case_is_beaten_by_the_canned_hedge() -> None:
    """The reference always-hedge responder must not score a capability point."""
    beaten = _beaten_by(lambda _case: CANNED_HEDGE)
    assert not beaten, (
        "these capability cases pass on the canned hedge: "
        + ", ".join(beaten)
        + " — see scripts/hedge_responder_probe.py::CANNED_HEDGE for the text."
    )


def test_gameable_baseline_has_no_stale_entries() -> None:
    """A repaired case must leave the baseline in the same commit that repairs it."""
    cases = {c["case_id"]: c for c in _capability_cases()}
    unknown = sorted(GAMEABLE_BASELINE - set(cases))
    assert not unknown, "GAMEABLE_BASELINE names cases that no longer exist: " + ", ".join(unknown)

    still_gameable: set[str] = set()
    for case_id in GAMEABLE_BASELINE:
        case = cases[case_id]
        for text in (case["input"]["player_message"], CANNED_HEDGE):
            if score_case(case, synthetic_response(text))["passed"]:
                still_gameable.add(case_id)
    repaired = sorted(GAMEABLE_BASELINE - still_gameable)
    assert not repaired, (
        "these cases now resist both the echo and the hedge but are still baselined: "
        + ", ".join(repaired)
        + " — delete them from GAMEABLE_BASELINE to ratchet the gate down."
    )


def test_every_capability_case_carries_relevant_node_ids_or_is_baselined() -> None:
    """EVAL-P20.2 validation (3): new cases must be annotated for the retrieval cross-tab."""
    missing = sorted(
        case["case_id"]
        for case in _capability_cases()
        if case["case_id"] not in GAMEABLE_BASELINE
        and not (isinstance(case.get("relevant_node_ids"), list) and case["relevant_node_ids"])
    )
    assert not missing, "capability cases without a relevant_node_ids annotation: " + ", ".join(missing)


@pytest.mark.parametrize("case", _capability_cases(), ids=lambda c: c["case_id"])
def test_every_capability_case_declares_a_content_judge(case: dict) -> None:
    """`schema` alone is satisfied by any non-empty string, so it can never be the
    only expectation on a capability case."""
    kinds = {exp.get("kind") for exp in case.get("expected", [])}
    assert kinds - {"schema"}, f"{case['case_id']} has no content judge beyond schema"
