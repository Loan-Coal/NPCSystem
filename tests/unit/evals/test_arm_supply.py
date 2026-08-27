"""
Module: tests.unit.evals.test_arm_supply
Layer: test (unit)
Purpose: Pin the supply arithmetic the pre-declaration report prints — the number that
         decides whether a candidate knob can be an arm at all (DEC-214).
Dependencies: pytest; evals.arm_supply
Used by: make test (pytest discovery)

The supplies used below are the ones measured on the clean eval baseline over the 8-NPC
probe roster, corpus_sha 2b19e47a1755354e:

    rag_top_k     supply 5 6 4 5 8 3 3 4   against a default ceiling of 5
    events_limit  supply 1 2 1 1 2 0 0 0   against a default ceiling of 5

Both retired arms are reproduced here as regression cases, because "the report would have
caught it" is worth exactly as much as a test that shows it doing so.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from arm_supply import summarize_knob  # noqa: E402

_RAG_SUPPLY = (5, 6, 4, 5, 8, 3, 3, 4)
_EVENT_SUPPLY = (1, 2, 1, 1, 2, 0, 0, 0)
_DEFAULT_CEILING = 5


def test_the_retired_wide_events_arm_is_reported_dead_in_both_directions() -> None:
    """No Character knows more than 2 events against a default limit of 5, and one knows
    zero, so there is no value of `events_limit` that changes anything on the roster."""
    summary = summarize_knob(
        knob="events_limit", default_ceiling=_DEFAULT_CEILING, supplies=_EVENT_SUPPLY
    )
    assert summary.raise_exposed_npcs == 0
    assert summary.largest_full_roster_lower_value is None
    assert summary.can_be_an_arm is False


def test_the_retired_wide_rag_arm_is_reported_exposed_on_a_minority() -> None:
    """`wide_rag` was not dead, it was PARTIAL — 2 of 8 NPCs had spare supply and neither
    probe case did. That is why a 2-case probe read it as a flat zero."""
    summary = summarize_knob(
        knob="rag_top_k", default_ceiling=_DEFAULT_CEILING, supplies=_RAG_SUPPLY
    )
    assert summary.raise_exposed_npcs == 2
    assert summary.raise_exposed_npcs < summary.roster_size


def test_the_largest_lower_value_that_binds_on_every_npc_is_reported() -> None:
    """A cut binds on an NPC only below BOTH its supply and the default ceiling, so the
    full-roster value is one under the smaller of (minimum supply, default ceiling).

    Minimum supply is 3, ceiling is 5, so 2 is the largest value that binds on all
    eight — which is exactly what `narrow_rag` ships.
    """
    summary = summarize_knob(
        knob="rag_top_k", default_ceiling=_DEFAULT_CEILING, supplies=_RAG_SUPPLY
    )
    assert summary.largest_full_roster_lower_value == 2
    assert summary.can_be_an_arm is True


def test_a_knob_whose_supply_is_everywhere_above_the_ceiling_can_raise() -> None:
    """The report must not be a one-way ratchet: on a world with real supply, raising is
    a legitimate arm and must be reported as one."""
    summary = summarize_knob(
        knob="rag_top_k", default_ceiling=2, supplies=(9, 9, 9, 9)
    )
    assert summary.raise_exposed_npcs == 4
    assert summary.largest_full_roster_lower_value == 1
    assert summary.can_be_an_arm is True


def test_an_empty_roster_is_not_reported_as_a_usable_knob() -> None:
    """Measuring nothing must not read as measuring zero exposure — that is the silent
    pass this whole phase exists to prevent."""
    summary = summarize_knob(knob="rag_top_k", default_ceiling=5, supplies=())
    assert summary.roster_size == 0
    assert summary.can_be_an_arm is False
