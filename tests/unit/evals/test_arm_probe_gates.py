"""
Module: tests.unit.evals.test_arm_probe_gates
Layer: test (unit)
Purpose: Pin the two gates that decide things rather than delegating to pytest — gate 2
         (corpus) and gate 4 (effect) — and in particular that neither can pass silently
         on an empty input.
Dependencies: pytest; evals.arm_probe_gates, evals.arm_probe_models
Used by: make test (pytest discovery)

The specific failure this module guards: a cache-isolation test passes trivially when
every arm retrieves nothing, and tierB.items was 0 on EVERY run ever recorded before P8.
So "the gates were green" has already been true of a system in which nothing was being
measured. Gate 4 must fail on that state, not pass.

Does NOT: hit the engine, run pytest as a subprocess, or read the corpus.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from arm_probe_gates import gate_2_corpus, gate_4_effect  # noqa: E402
from arm_probe_models import ArmObservation, TierRow  # noqa: E402

_SHA = "2b19e47a1755354e782d289d01aaae731a90321406972fdc686fb660663a8b20"


def _observation(
    npc_id: str, arm: str, *, tier_b: int, keys: tuple[str, ...]
) -> ArmObservation:
    return ArmObservation(
        arm=arm,
        npc_id=npc_id,
        query="what news",
        item_keys=keys,
        tier_spend=(
            TierRow(tier="tier0", items=3, tokens=93),
            TierRow(tier="tierA", items=8, tokens=687),
            TierRow(tier="tierB", items=tier_b, tokens=93 if tier_b else 0),
            TierRow(tier="tierC", items=3, tokens=140),
        ),
        total_tokens=1013,
    )


# ---------------------------------------------------------------------------
# Gate 4 — effect
# ---------------------------------------------------------------------------


def test_gate_4_fails_when_an_arm_matches_default_on_every_case() -> None:
    """The arm is not an arm. Config-differs does not imply retrieval-differs: a knob can
    be inert (graph_rag_top_k while GRAPH_RAG_ENABLED is False) or have no exposure."""
    keys = ("world", "beliefs", "rag:a")
    default = [_observation("captain_sorn", "default", tier_b=2, keys=keys)]
    result = gate_4_effect(
        default_runs=default,
        arm_runs={"wide_rag": [_observation("captain_sorn", "wide_rag", tier_b=2, keys=keys)]},
        expects_rag={"wide_rag": True},
    )
    assert result.passed is False
    assert any("IDENTICAL to default" in line for line in result.detail)


def test_gate_4_fails_when_both_runs_carry_zero_tier_b_items() -> None:
    """THE gate. item_keys differ, so a naive check passes — but with tier B empty in
    both runs the difference is tier-A noise and says nothing about retrieval.

    This is the state every run before P8 was in.
    """
    default = [_observation("captain_sorn", "default", tier_b=0, keys=("world", "beliefs"))]
    arm = [_observation("captain_sorn", "wide_rag", tier_b=0, keys=("world", "goals"))]
    result = gate_4_effect(
        default_runs=default, arm_runs={"wide_rag": arm}, expects_rag={"wide_rag": True}
    )
    assert result.passed is False
    assert any("ZERO tier-B items in BOTH runs" in line for line in result.detail)


def test_gate_4_fails_when_a_rag_arm_assembles_no_tier_b_items() -> None:
    """A RAG arm with an empty tier B has not exercised the mechanism it names, even if
    default's tier B is full and the keys differ."""
    default = [_observation("captain_sorn", "default", tier_b=2, keys=("world", "rag:a"))]
    arm = [_observation("captain_sorn", "wide_rag", tier_b=0, keys=("world",))]
    result = gate_4_effect(
        default_runs=default, arm_runs={"wide_rag": arm}, expects_rag={"wide_rag": True}
    )
    assert result.passed is False
    assert any("RAG arm assembled zero tier-B items" in line for line in result.detail)


def test_gate_4_fails_when_a_no_rag_arm_retrieves_anyway() -> None:
    """`no_rag`'s entire mechanism is skip_rag. If tier B is non-empty under it, the arm
    did not run the configuration it claims — DEC-194's defect class."""
    default = [_observation("captain_sorn", "default", tier_b=2, keys=("world", "rag:a"))]
    arm = [_observation("captain_sorn", "no_rag", tier_b=2, keys=("world", "rag:b"))]
    result = gate_4_effect(
        default_runs=default, arm_runs={"no_rag": arm}, expects_rag={"no_rag": False}
    )
    assert result.passed is False
    assert any("no-RAG arm assembled tier-B items anyway" in line for line in result.detail)


def test_gate_4_passes_a_genuine_no_rag_contrast() -> None:
    """The arm that should pass: default retrieves, no_rag does not, keys differ."""
    default = [_observation("captain_sorn", "default", tier_b=2, keys=("world", "rag:a"))]
    arm = [_observation("captain_sorn", "no_rag", tier_b=0, keys=("world",))]
    result = gate_4_effect(
        default_runs=default, arm_runs={"no_rag": arm}, expects_rag={"no_rag": False}
    )
    assert result.passed is True


def test_gate_4_reports_the_supply_when_an_arm_has_no_exposure() -> None:
    """"The arm did nothing" and "there was nothing for the arm to take" are different
    findings with different remedies, and only the second is a property of the world.

    Measured on the eval baseline: every NPC knows <=2 events against an events_limit of
    5, so `wide_events` at 15 cannot add a row that does not exist.
    """
    keys = ("world", "event:0:captain_sorn", "rag:a", "rag:b")
    default = [_observation("captain_sorn", "default", tier_b=2, keys=keys)]
    arm = [_observation("captain_sorn", "wide_events", tier_b=2, keys=keys)]
    result = gate_4_effect(
        default_runs=default, arm_runs={"wide_events": arm}, expects_rag={"wide_events": True}
    )
    assert result.passed is False
    assert any("event:=1 rag:=2" in line for line in result.detail)
    assert any("NO EXPOSURE" in line for line in result.detail)


def test_gate_4_fails_on_an_empty_observation_set() -> None:
    """An empty probe must not read as a pass. This is the whole brief in one assertion."""
    assert gate_4_effect(default_runs=[], arm_runs={}, expects_rag={}).passed is False


# ---------------------------------------------------------------------------
# Gate 2 — corpus
# ---------------------------------------------------------------------------


class _FakeClient:
    """Stands in for ProbeClient with a scripted rehydrate report and fingerprint."""

    def __init__(self, *, nodes_read: int = 51) -> None:
        self._nodes_read = nodes_read

    def rehydrate(self) -> dict[str, Any]:
        return {
            "nodes_read": self._nodes_read,
            "upserted": self._nodes_read,
            "missing_embedding": 0,
            "reconcile_passes": 1,
        }

    def corpus_fingerprint(self) -> dict[str, Any]:
        return {}


def _fields(**overrides: Any):
    """Return a corpus_fields stand-in yielding one fixed record per call."""
    base = {
        "corpus_item_count": 51,
        "corpus_embedding_model": "all-MiniLM-L6-v2",
        "corpus_embedding_dim": 384,
        "corpus_sha": _SHA,
    }
    base.update(overrides)
    return lambda _fetch: dict(base)


def test_gate_2_passes_a_populated_corpus_that_is_identical_across_arms() -> None:
    """The state DEC-212 measured: 51 items, one model, one sha, reproducible."""
    result = gate_2_corpus(
        client=_FakeClient(), arms=["default", "no_rag"], corpus_fields=_fields()
    )
    assert result.passed is True


def test_gate_2_fails_an_empty_corpus() -> None:
    """item_count 0 means every arm retrieves nothing, which makes gates 3 and 4 vacuous.
    That is exactly why this gate goes SECOND rather than last."""
    result = gate_2_corpus(
        client=_FakeClient(), arms=["default"], corpus_fields=_fields(corpus_item_count=0)
    )
    assert result.passed is False
    assert any("item_count is 0" in line for line in result.detail)


def test_gate_2_fails_an_empty_sha_rather_than_calling_it_identical() -> None:
    """Four empty strings are identical across arms. Accepting that would make the gate
    decorative — and the route returned corpus_sha='' unconditionally until P9."""
    result = gate_2_corpus(
        client=_FakeClient(), arms=["default", "no_rag"], corpus_fields=_fields(corpus_sha="")
    )
    assert result.passed is False
    assert any("corpus_sha is EMPTY" in line for line in result.detail)


def test_gate_2_fails_when_the_fingerprint_moves_between_arms() -> None:
    """paired_arms interleaves arms inside one run, so a corpus that moved mid-run lands
    unevenly across arms and is indistinguishable from a treatment effect (DEC-210)."""
    shas = iter([_SHA, "0" * 64])

    def moving(_fetch: Any) -> dict[str, Any]:
        return {
            "corpus_item_count": 51,
            "corpus_embedding_model": "all-MiniLM-L6-v2",
            "corpus_embedding_dim": 384,
            "corpus_sha": next(shas),
        }

    result = gate_2_corpus(
        client=_FakeClient(), arms=["default", "no_rag"], corpus_fields=moving
    )
    assert result.passed is False
    assert any("corpus_sha DIFFERS across arms" in line for line in result.detail)


def test_gate_2_fails_when_rehydrate_reads_nothing() -> None:
    """A silent empty corpus costs a night of generation and then reads as a null result."""
    result = gate_2_corpus(
        client=_FakeClient(nodes_read=0), arms=["default"], corpus_fields=_fields()
    )
    assert result.passed is False
    assert any("ZERO nodes" in line for line in result.detail)


def test_gate_2_fails_when_the_engine_could_not_be_asked() -> None:
    """corpus_fields returns {} when the engine is unreachable, which is DELIBERATELY
    distinct from a zero item_count. A run that could not ask must not look like a run
    that asked and found nothing."""
    result = gate_2_corpus(
        client=_FakeClient(), arms=["default"], corpus_fields=lambda _fetch: {}
    )
    assert result.passed is False
    assert any("could not be asked" in line for line in result.detail)
