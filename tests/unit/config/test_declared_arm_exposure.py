"""
Module: test_declared_arm_exposure
Layer: test (unit)
Purpose: Pin the DESIGN-TIME half of DEC-214's rule — every declared A/B arm records the
         supply it was sized against, and the recorded arithmetic must imply exposure.
Dependencies: pytest, pydantic; npc_engine.schema (load_llm_config, ArmExposureRecord)
Used by: pytest (make test / make check)

WHAT THIS CAN AND CANNOT CHECK, STATED HONESTLY

`wide_events` and `wide_rag` were declared with no exposure and stayed declared for a
whole phase. Gate 4 of `make eval-arm-probe` caught them, but only at runtime, against a
live engine and a seeded world — which means the defect could be introduced in a commit
and survive until someone happened to run the probe.

CAN be checked here, with no engine and no world:
  * every declared arm has an exposure record, and every record names a declared arm;
  * the record names the field the arm ACTUALLY varies against the default profile, so a
    record cannot drift away from the arm it describes;
  * the recorded numbers are internally consistent with the direction claimed — a raise
    above the recorded supply, or a lower above the recorded ceiling, is a contradiction
    visible in the YAML itself;
  * exposure was measured on the WHOLE roster, not on a lucky subset. `wide_rag` would
    have recorded 2/8 here, and 2/8 is precisely why a 2-case probe reported 0/2.

CANNOT be checked here, ever:
  * whether the recorded supply is still TRUE of the live world. A reseed, a new corpus,
    or a scope change can invalidate every number in the block and nothing static can
    know. That is what gate 4 is for, and why the record carries the corpus_sha it was
    measured against — a mismatch there is the signal to re-measure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from npc_engine.schema.arm_exposure_models import ArmExposureRecord
from npc_engine.schema.llm_schema_loader import load_llm_config
from npc_engine.schema.retrieval_profile_models import build_default_profile

_DEFAULT_RAG_TOP_K: int = 5
_DEFAULT_CROSS_ENCODER: bool = False
_SHIPPED_CONFIG: str = "config/llm_config.yaml"


def _shipped_config():
    package_root = Path(__file__).resolve().parents[3] / "src" / "npc_engine"
    return load_llm_config(config_path=str(package_root / _SHIPPED_CONFIG))


def _varied_field(arm) -> set[str]:
    """Return the profile fields this arm actually differs from the default in."""
    default = build_default_profile(
        rag_top_k=_DEFAULT_RAG_TOP_K, cross_encoder_enabled=_DEFAULT_CROSS_ENCODER
    )
    return {
        field
        for field in type(default).model_fields
        if getattr(arm, field) != getattr(default, field)
    }


# ---------------------------------------------------------------------------
# The ledger covers the arms, and only the arms
# ---------------------------------------------------------------------------


def test_every_declared_arm_records_the_supply_it_was_sized_against() -> None:
    """An arm with no exposure record is an arm nobody measured, which is exactly how
    `wide_events` and `wide_rag` came to be declared (DEC-214)."""
    config = _shipped_config()
    missing = sorted(set(config.retrieval_profiles) - set(config.retrieval_profile_exposure))
    assert not missing, (
        f"declared arm(s) {missing} have no entry in retrieval_profile_exposure: — "
        f"measure the supply first, size the knob against it, then declare"
    )


def test_the_ledger_has_no_record_for_an_arm_that_is_not_declared() -> None:
    """A record left behind by a retired arm would make the block read as authoritative
    while describing something the engine can no longer run."""
    config = _shipped_config()
    orphans = sorted(set(config.retrieval_profile_exposure) - set(config.retrieval_profiles))
    assert not orphans, (
        f"retrieval_profile_exposure: describes {orphans}, which no longer appear in "
        f"retrieval_profiles: — retire the record with the arm"
    )


def test_each_record_names_the_field_its_arm_actually_varies() -> None:
    """Without this the record can drift: an arm could be re-pointed at another knob and
    keep a supply table measured for the old one."""
    config = _shipped_config()
    for name, arm in config.retrieval_profiles.items():
        record = config.retrieval_profile_exposure[name]
        varied = _varied_field(arm)
        assert record.knob in varied, (
            f"{name!r} records exposure for knob {record.knob!r}, but the arm actually "
            f"varies {sorted(varied)}"
        )


def test_every_arm_was_measured_exposed_on_the_whole_roster() -> None:
    """Partial exposure is what made the defect invisible.

    `wide_rag` had headroom on 2 of 8 NPCs — mira_innkeeper and lira_fence, the only two
    with spare supply — and zero on both probe cases. A 2-case probe cannot sample a 2/8
    effect reliably, so an arm is only accepted here when it was measured to bind on
    every NPC on the roster. An arm that genuinely needs partial exposure has to change
    this rule deliberately rather than slip past it.
    """
    for name, record in _shipped_config().retrieval_profile_exposure.items():
        assert record.exposed_npcs == record.roster_size, (
            f"{name!r} was measured exposed on {record.exposed_npcs}/{record.roster_size} "
            f"NPCs; a probe of 2 cases cannot resolve that"
        )


# ---------------------------------------------------------------------------
# The record's own arithmetic
# ---------------------------------------------------------------------------


def test_a_raise_above_the_recorded_supply_is_rejected_at_load() -> None:
    """THE DEFECT, AS A UNIT TEST. This is `wide_events`: events_limit 5 -> 15 against a
    world where no Character knows more than 2 events."""
    with pytest.raises(ValidationError, match="above the measured supply"):
        ArmExposureRecord(
            knob="events_limit",
            direction="raise",
            default_ceiling=5,
            arm_value=15,
            measured_supply_min=0,
            measured_supply_max=2,
            exposed_npcs=8,
            roster_size=8,
            measured_on_corpus_sha="2b19e47a1755354e",
            note="the retired wide_events arm",
        )


def test_a_lower_that_is_not_actually_lower_is_rejected_at_load() -> None:
    """A 'lower' at or above the default ceiling changes nothing and is a typo, not an arm."""
    with pytest.raises(ValidationError, match="not below the default ceiling"):
        ArmExposureRecord(
            knob="rag_top_k",
            direction="lower",
            default_ceiling=5,
            arm_value=5,
            measured_supply_min=3,
            measured_supply_max=8,
            exposed_npcs=8,
            roster_size=8,
            measured_on_corpus_sha="2b19e47a1755354e",
            note="",
        )


def test_a_withhold_record_must_not_claim_a_ceiling() -> None:
    """`skip_rag` and `disabled_slots` have no numeric ceiling; recording one would
    invite the raise/lower arithmetic to be applied to a knob it does not describe."""
    with pytest.raises(ValidationError, match="carries no ceiling"):
        ArmExposureRecord(
            knob="skip_rag",
            direction="withhold",
            default_ceiling=5,
            arm_value=0,
            measured_supply_min=3,
            measured_supply_max=5,
            exposed_npcs=8,
            roster_size=8,
            measured_on_corpus_sha="2b19e47a1755354e",
            note="",
        )


def test_an_arm_measured_exposed_on_nothing_is_rejected_at_load() -> None:
    """Zero exposure is not a small effect. It is a guaranteed null and a wasted run."""
    with pytest.raises(ValidationError):
        ArmExposureRecord(
            knob="skip_rag",
            direction="withhold",
            measured_supply_min=0,
            measured_supply_max=0,
            exposed_npcs=0,
            roster_size=8,
            measured_on_corpus_sha="2b19e47a1755354e",
            note="",
        )


def test_the_shipped_records_all_name_the_corpus_they_were_measured_on() -> None:
    """A supply number without the corpus it was measured against cannot be re-checked
    after a reseed, and DEC-210 makes the corpus the thing an eval run freezes."""
    for name, record in _shipped_config().retrieval_profile_exposure.items():
        assert record.measured_on_corpus_sha, f"{name!r} records no corpus_sha"
