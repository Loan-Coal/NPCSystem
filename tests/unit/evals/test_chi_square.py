"""
Module: test_chi_square
Layer: test (unit)
Purpose: Tests for evals/chi_square.py — chi-square upper-tail probability against
         well-known textbook critical values.
Dependencies: pytest, chi_square (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from chi_square import chi2_sf

# Standard chi-square critical values at alpha=0.05, from any statistics textbook table.
_CRITICAL_VALUES_ALPHA_05 = {1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070}


@pytest.mark.parametrize("df,critical", _CRITICAL_VALUES_ALPHA_05.items())
def test_chi2_sf_matches_known_critical_values(df: int, critical: float) -> None:
    """chi2_sf(critical_value, df) is close to 0.05 for standard table values."""
    assert chi2_sf(critical, df) == pytest.approx(0.05, abs=2e-4)


def test_chi2_sf_at_zero_is_one() -> None:
    """x=0 always has full mass to the right — p=1.0."""
    assert chi2_sf(0.0, df=3) == 1.0


def test_chi2_sf_at_negative_x_is_one() -> None:
    """A statistic of 0 or below always yields the maximal p-value."""
    assert chi2_sf(-1.0, df=3) == 1.0


def test_chi2_sf_decreases_with_x() -> None:
    """A larger statistic is always less likely under H0."""
    assert chi2_sf(5.0, df=3) > chi2_sf(10.0, df=3)


def test_chi2_sf_df_one_matches_normal_tail() -> None:
    """chi-square(1) is the square of a standard normal; z=1.96 -> x=3.8416 -> p~0.05."""
    assert chi2_sf(3.8416, df=1) == pytest.approx(0.05, abs=1e-3)


def test_chi2_sf_invalid_df_raises() -> None:
    """df must be positive."""
    with pytest.raises(ValueError):
        chi2_sf(1.0, df=0)
