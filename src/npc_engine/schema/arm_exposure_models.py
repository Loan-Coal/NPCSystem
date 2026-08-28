"""
Module: arm_exposure_models
Layer: config
Purpose: The measured supply an A/B arm was sized against — the design-time half of the
         rule that an arm may not be declared until its exposure has been measured.
Dependencies: pydantic
Used by: schema/context_config_models (LLMConfig.retrieval_profile_exposure),
         tests/unit/config/test_declared_arm_exposure.py

Does NOT: read files, touch the graph, retrieve anything, or resolve a profile. It is a
record OF a measurement, never the measurement.
Dependencies injected: None — every field arrives from the YAML the loader validates,
matching the sibling convention in retrieval_profile_models.py, so this module stays pure.

WHY THIS EXISTS (DEC-214)

Two declared arms — `wide_events` (events_limit 5 -> 15) and `wide_rag` (rag_top_k
5 -> 15) — produced context BYTE-IDENTICAL to the default profile on every probe case,
for a whole phase, without anything objecting. Neither was misconfigured. Each RAISED A
CEILING ABOVE ITS OWN SUPPLY:

    knob           default   measured supply on the eval world   headroom to RAISE
    events_limit         5   max 2 known by ANY Character         0 on 8/8 NPCs
    rag_top_k            5   3-8 candidates per NPC               0 on 6/8 NPCs

They were sized against JUDGE RESOLUTION rather than supply, because supply was not a
knowable quantity when they were written: tier B carried zero items on every run ever
recorded (DEC-208), so "does this arm change anything?" had no answer. The wrong axis was
the only axis available.

WHAT A RECORD BUYS, AND WHAT IT DOES NOT

It cannot prove the supply is still what it says — a reseed, a corpus change or a scope
change invalidates every number here, and nothing static can know. `measured_on_corpus_sha`
is what makes that detectable: when the live corpus no longer matches, the record is stale
and must be re-measured rather than trusted. Gate 4 of `make eval-arm-probe` remains the
runtime check.

What it does buy is that the arithmetic is checkable in the file itself. A raise whose
recorded supply does not exceed the recorded default ceiling is a contradiction, and a
contradiction can be rejected at load time — years before anyone runs a probe.

DIRECTIONS

    raise     the arm INCREASES a numeric ceiling. Needs supply above the default
              ceiling, or there is nothing for the raise to take.
    lower     the arm DECREASES a numeric ceiling. Needs supply above the ARM's value,
              or there is nothing for the cut to remove, and the arm value must actually
              be below the default or it is not a cut at all.
    withhold  the arm removes a whole class of items (`skip_rag`, `disabled_slots`).
              There is no numeric ceiling; recording one would invite the raise/lower
              arithmetic to be applied to a knob that does not have it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["ARM_EXPOSURE_DIRECTIONS", "ArmExposureDirection", "ArmExposureRecord"]

ArmExposureDirection = Literal["raise", "lower", "withhold"]
"""How an arm takes its exposure from the supply it was measured against."""

ARM_EXPOSURE_DIRECTIONS: frozenset[str] = frozenset({"raise", "lower", "withhold"})
"""Every declarable direction, for callers that need to enumerate them."""

_CEILING_DIRECTIONS: frozenset[str] = frozenset({"raise", "lower"})
"""Directions that describe a numeric ceiling and therefore require one."""


class ArmExposureRecord(BaseModel):
    """The measured supply one declared A/B arm was sized against.

    Attributes:
        knob: The single RetrievalProfile field this arm varies. Checked against the
            arm's actual difference from the default profile by
            test_each_record_names_the_field_its_arm_actually_varies.
        direction: How the arm takes exposure — see the module docstring.
        default_ceiling: The default profile's value of this knob, for a ceiling knob.
            None for a `withhold` arm, which has no ceiling.
        arm_value: This arm's value of the knob. None for a `withhold` arm.
        measured_supply_min: Smallest supply observed across the measured roster.
        measured_supply_max: Largest supply observed across the measured roster.
        exposed_npcs: How many roster NPCs the arm was measured to actually change.
        roster_size: How many NPCs were measured. A supply table over two NPCs cannot
            support a claim about a world, which is how a 2-of-8 effect read as zero.
        measured_on_corpus_sha: The corpus fingerprint these numbers were taken against.
            A live corpus that no longer matches means the record is stale, not wrong.
        note: One line of prose recording what was actually observed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    knob: str = Field(min_length=1)
    direction: ArmExposureDirection
    default_ceiling: int | None = None
    arm_value: int | None = None
    measured_supply_min: int = Field(ge=0)
    measured_supply_max: int = Field(ge=0)
    exposed_npcs: int = Field(gt=0)
    roster_size: int = Field(gt=0)
    measured_on_corpus_sha: str = Field(min_length=1)
    note: str = ""

    @model_validator(mode="after")
    def _validate_record(self) -> "ArmExposureRecord":
        """Reject a record whose own numbers contradict the exposure it claims."""
        if self.measured_supply_min > self.measured_supply_max:
            raise ValueError(
                f"measured_supply_min {self.measured_supply_min} exceeds "
                f"measured_supply_max {self.measured_supply_max}"
            )
        if self.exposed_npcs > self.roster_size:
            raise ValueError(
                f"exposed_npcs {self.exposed_npcs} exceeds roster_size {self.roster_size}"
            )
        self._validate_ceiling_presence()
        if self.default_ceiling is not None and self.arm_value is not None:
            self._validate_direction_arithmetic(
                ceiling=self.default_ceiling, value=self.arm_value
            )
        return self

    def _validate_ceiling_presence(self) -> None:
        """Require a ceiling for raise/lower and forbid one for withhold."""
        has_ceiling = self.default_ceiling is not None and self.arm_value is not None
        if self.direction in _CEILING_DIRECTIONS and not has_ceiling:
            raise ValueError(
                f"direction {self.direction!r} needs both default_ceiling and arm_value"
            )
        if self.direction not in _CEILING_DIRECTIONS and (
            self.default_ceiling is not None or self.arm_value is not None
        ):
            raise ValueError(
                f"knob {self.knob!r} carries no ceiling, so a {self.direction!r} record "
                f"must leave default_ceiling and arm_value unset"
            )

    def _validate_direction_arithmetic(self, *, ceiling: int, value: int) -> None:
        """Reject a ceiling move that the recorded supply says cannot take anything.

        Args:
            ceiling: The default profile's value, already narrowed to non-None.
            value: This arm's value, already narrowed to non-None.
        """
        if self.direction == "raise":
            self._require(value > ceiling, "does not raise the default ceiling")
            self._require(
                self.measured_supply_max > ceiling,
                "is above the measured supply — there is nothing for the raise to take",
            )
        elif self.direction == "lower":
            self._require(value < ceiling, "is not below the default ceiling")
            self._require(
                value < self.measured_supply_max,
                "is above the measured supply — there is nothing for the cut to remove",
            )

    def _require(self, condition: bool, complaint: str) -> None:
        if not condition:
            raise ValueError(
                f"{self.knob}={self.arm_value} against default {self.default_ceiling} "
                f"and supply {self.measured_supply_min}-{self.measured_supply_max}: "
                f"the arm value {complaint}"
            )
