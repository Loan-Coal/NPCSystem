"""
Module: reset_fidelity_record
Layer: evals (eval harness — not part of src/)
Purpose: The evals/reset_fidelity.json artifact model and the tier rule behind
         it (EVAL-P12.1). Records what a world reset actually cleared, what
         survived it, what could not be observed at all, and how long it took —
         so evals/sequence_runner.py can decide whether k repetitions are
         independent instead of assuming it.
Dependencies: pydantic, stdlib (typing)
Used by: e2e/scripts/measure_reset_fidelity.py (writes it),
         evals/sequence_fidelity.py (EVAL-P12.4, reads it)

WHY THE TIER IS VALIDATED RATHER THAN ASSIGNED
----------------------------------------------
docs/SEQUENCE_STATS_POLICY.md §2 admits exactly two tiers: FULL only if
**nothing** survives, PARTIAL for everything else. There is no third. EVAL-P12.1
names the failure mode precisely — "a tier chosen because it keeps a metric alive
is the single worst outcome available here, and it would be invisible to every
gate in the repo". So `fidelity` is cross-checked against `surviving` by a model
validator: a report claiming FULL while anything survived cannot be constructed,
and neither can its inverse. The tier is evidence, not a declaration.

An **unobservable** store is not an absent one. A store the API exposes no read
endpoint for is recorded as `unknown:<name>` in `surviving`, which keeps the tier
PARTIAL. Dropping it instead is exactly how PARTIAL becomes a false FULL.

FIELD NAMES
-----------
`cleared`, `surviving` and `duration_ms` are ResetReceipt's field names verbatim
(evals/sequence_records.py), so the whole document validates into a ResetReceipt
with no translation layer — the EVAL-P12.1 validation. `fidelity`, `measured_at`
and `git_sha` are run-level provenance ResetReceipt has no place for; Pydantic's
default extra='ignore' passes them over. Resolved 2026-08-10 with the human;
see DEC-166.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

# Marker for a store whose post-reset state could not be read, because the API
# exposes no endpoint for it. Not a survivor and not a non-survivor: unknown.
UNKNOWN_PREFIX: str = "unknown:"

FidelityTier = Literal["FULL", "PARTIAL"]


def mark_unknown(store_name: str) -> str:
    """Tag a store as unobservable for the `surviving` list.

    Args:
        store_name: Name of the in-process store or graph region.
    Returns:
        The name prefixed with UNKNOWN_PREFIX.
    """
    return f"{UNKNOWN_PREFIX}{store_name}"


def assign_tier(surviving: tuple[str, ...]) -> FidelityTier:
    """Derive the reset fidelity tier from what survived.

    Args:
        surviving: Everything that outlived the reset, including `unknown:`
            entries for stores that could not be observed.
    Returns:
        'FULL' if and only if `surviving` is empty; 'PARTIAL' otherwise.
    """
    return "FULL" if not surviving else "PARTIAL"


class ResetFidelityReport(BaseModel):
    """One measurement of what `preconditions.reset_world` actually clears.

    Serialises to evals/reset_fidelity.json. The whole document validates into
    `sequence_records.ResetReceipt` unchanged.

    Attributes:
        fidelity: 'FULL' or 'PARTIAL'. Cross-checked against `surviving`.
        cleared: State components observed to be fully reset.
        surviving: State that outlived the reset. Entries prefixed `unknown:`
            are stores the API cannot read, not stores known to survive.
        duration_ms: Measured wall-clock milliseconds for one reset call.
        measured_at: ISO-8601 timestamp of the measurement.
        git_sha: Short commit hash the measurement was taken at.
    """

    model_config = ConfigDict(frozen=True)

    fidelity: FidelityTier
    cleared: tuple[str, ...]
    surviving: tuple[str, ...]
    duration_ms: int
    measured_at: str
    git_sha: str

    @property
    def unobservable(self) -> tuple[str, ...]:
        """Names of stores recorded as unreadable, with the marker stripped."""
        return tuple(
            s.removeprefix(UNKNOWN_PREFIX) for s in self.surviving if s.startswith(UNKNOWN_PREFIX)
        )

    @property
    def observed_surviving(self) -> tuple[str, ...]:
        """Survivors that were actually measured, as opposed to unreadable."""
        return tuple(s for s in self.surviving if not s.startswith(UNKNOWN_PREFIX))

    @model_validator(mode="after")
    def _tier_must_match_the_evidence(self) -> ResetFidelityReport:
        """Refuse a tier that contradicts `surviving`, in either direction."""
        derived = assign_tier(self.surviving)
        if self.fidelity != derived:
            raise ValueError(
                f"fidelity={self.fidelity!r} contradicts the evidence: "
                f"{len(self.surviving)} item(s) survived "
                f"({', '.join(self.surviving) or 'none'}), so the tier is {derived!r}. "
                f"SEQUENCE_STATS_POLICY §2 admits no third tier and no discretion here."
            )
        return self
