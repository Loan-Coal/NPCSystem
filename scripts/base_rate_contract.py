"""
Module: base_rate_contract
Layer: scripts (dev tooling — imports nothing outside the stdlib and pydantic)
Purpose: EVAL-P25.3's contract: the target pass base rate declared in
         docs/CASE_SET_POLICY.md, the band arithmetic that decides whether a measured
         rate sits inside it, and the Pydantic models the measurement crosses module
         boundaries in. Holds no I/O.
Dependencies: enum, fractions, math; pydantic.
Used by: scripts/check_base_rate.py (which re-exports this module's public names),
         tests/unit/scripts/test_check_base_rate.py.

Split from `check_base_rate.py` to keep both files inside CLAUDE.md's 300-line limit and
each to one category: this module is the contract and its data model, `check_base_rate`
is the reader and the gate. The public surface is unchanged — import either from here or
from `check_base_rate`, which re-exports all of it.
"""

from __future__ import annotations

import enum
import math
from fractions import Fraction

from pydantic import BaseModel, ConfigDict

# --- The band ---

#: Target pass base rate. Below TARGET_BAND_LOW the battery is measuring engine failure
#: rather than engine capability; above TARGET_BAND_HIGH it is on the kappa ceiling, where
#: expected chance agreement Pe swamps the statistic and kappa is suppressed regardless of
#: how well the scorer actually agrees.
TARGET_BAND_LOW: float = 0.55
TARGET_BAND_HIGH: float = 0.85

#: Enforcement modes. `advisory` reports and exits 0; `blocking` exits 1 on any breach;
#: `ratchet` exits 1 only when the measurement is WORSE than the recorded baseline.
ADVISORY: str = "advisory"
BLOCKING: str = "blocking"
RATCHET: str = "ratchet"
ENFORCEMENT_MODES: tuple[str, ...] = (ADVISORY, BLOCKING, RATCHET)

#: Shipped default (R2.3). Ratchet, not advisory: advisory's promotion criterion named
#: EVAL-P26, a phase DEC-233 culled, so it would never have fired — the same
#: never-promoted-advisory pattern R1 removed three times. Not blocking either: the
#: battery breaches nine families today for a defect no scheduled task fixes, so blocking
#: would red every downstream task through no fault of its own. The ratchet blocks from
#: day one, has no promotion criterion to forget, and lets the debt shrink but never grow.
DEFAULT_ENFORCEMENT: str = RATCHET

_EXIT_OK: int = 0
_EXIT_BREACH: int = 1


class EmptyGenerationError(ValueError):
    """Raised when a generation directory yields no scored rows.

    An unmeasured battery is never in band: "no row scored" and "every row passed" are
    the same absence of evidence and opposite conclusions.
    """


class BandStatus(enum.Enum):
    """Where a measured rate sits relative to the target band."""

    IN_BAND = "in_band"
    ABOVE_BAND = "above_band"
    BELOW_BAND = "below_band"
    INSUFFICIENT_N = "insufficient_n"


# --- Band arithmetic: the minimum n is derived from the band, never invented ---


def smallest_n_reaching_band(low: float, high: float) -> int:
    """Smallest record count for which some observable rate k/n lands inside [low, high].

    A family with fewer records than this cannot land in band however the engine behaves,
    so calling it a breach would be an artifact of the denominator. DEC-181 rejected an
    option for introducing an uncalibrated free parameter; this minimum is computed from
    the band rather than chosen, so there is nothing left to calibrate. Exact rational
    arithmetic keeps a boundary rate from being lost to floating-point rounding.

    Args:
        low: Inclusive lower edge of the band.
        high: Inclusive upper edge of the band.
    Returns:
        The smallest n >= 1 admitting an integer k with low <= k/n <= high.
    Raises:
        ValueError: If the band is empty (low > high) or outside [0, 1].
    """
    if not 0.0 <= low <= high <= 1.0:
        raise ValueError(f"invalid target band: [{low}, {high}] must satisfy 0 <= low <= high <= 1")
    lo, hi = Fraction(low), Fraction(high)
    # Any band of width d is reached by some k/n once n >= 1/d, so this bound terminates.
    ceiling = math.ceil(1.0 / (high - low)) + 1 if high > low else 1
    for n in range(1, ceiling + 1):
        if Fraction(math.ceil(lo * n), n) <= hi:
            return n
    raise ValueError(f"no n <= {ceiling} reaches band [{low}, {high}]")


def classify(passes: int, n: int, low: float, high: float) -> BandStatus:
    """Classify one measured rate against the band.

    Args:
        passes: Passing rows.
        n: Total scored rows.
        low: Inclusive lower band edge.
        high: Inclusive upper band edge.
    Returns:
        INSUFFICIENT_N when n is below `smallest_n_reaching_band`, else the verdict.
    """
    if n < smallest_n_reaching_band(low, high):
        return BandStatus.INSUFFICIENT_N
    rate = passes / n
    if rate < low:
        return BandStatus.BELOW_BAND
    return BandStatus.ABOVE_BAND if rate > high else BandStatus.IN_BAND


# --- Models ---


class BaseRateBaseline(BaseModel):
    """The recorded measurement a ratchet run is judged against.

    Attributes:
        gen_dir: Generation directory the baseline was recorded from. Recorded for
            provenance; re-pointing the ratchet at a newer generation is a deliberate
            human step, never automatic — an automatic re-point would let a worse
            generation launder itself into the baseline.
        overall_rate: Recorded whole-battery pass rate. A HIGHER rate is worse: the band
            is breached from above, where Pe swamps kappa.
        breaches: family -> BandStatus value, for every family out of band when recorded.
    """

    model_config = ConfigDict(frozen=True)

    gen_dir: str
    overall_rate: float
    breaches: dict[str, str]


class FamilyRate(BaseModel):
    """The measured pass rate for one matcher/expectation family.

    Attributes:
        family: The matcher_kind / judge_kind the rows were grouped by.
        n: Scored rows in this family.
        passes: Rows that passed.
        pass_rate: passes / n.
        status: Where `pass_rate` sits relative to the target band.
        has_variance: False when every row agrees (rate 0.0 or 1.0) — a constant family
            has nothing for any comparison to move, whatever its n.
    """

    model_config = ConfigDict(frozen=True)

    family: str
    n: int
    passes: int
    pass_rate: float
    status: BandStatus
    has_variance: bool


class BaseRateReport(BaseModel):
    """The full base-rate measurement over one generation directory.

    Attributes:
        gen_dir: Directory the rows were read from.
        band_low: Inclusive lower band edge in force for this run.
        band_high: Inclusive upper band edge in force for this run.
        enforcement: ADVISORY or BLOCKING.
        overall: The whole-battery rate, family name `ALL`.
        families: Per-family rates, largest n first.
        breaches: Families ABOVE_BAND or BELOW_BAND. Populated identically in every
            enforcement mode; only `exit_code` differs.
        baseline: The recorded measurement, when one was loaded. None outside ratchet mode.
        regressions: Human-readable reasons this run is worse than `baseline`. Empty when
            the run is at or better than baseline. Only ratchet mode consults it.
    """

    model_config = ConfigDict(frozen=True)

    gen_dir: str
    band_low: float
    band_high: float
    enforcement: str
    overall: FamilyRate
    families: tuple[FamilyRate, ...]
    breaches: tuple[FamilyRate, ...]
    baseline: BaseRateBaseline | None = None
    regressions: tuple[str, ...] = ()

    @property
    def exit_code(self) -> int:
        """0 in advisory always; 1 in blocking on any breach; 1 in ratchet on regression."""
        if self.enforcement == ADVISORY:
            return _EXIT_OK
        if self.enforcement == RATCHET:
            return _EXIT_BREACH if self.regressions else _EXIT_OK
        return _EXIT_BREACH if self.breaches else _EXIT_OK
