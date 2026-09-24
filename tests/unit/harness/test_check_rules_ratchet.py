"""
Module: test_check_rules_ratchet
Layer: harness (tests)
Purpose: Verify check_rules.py's baseline ratchet prunes resolved entries
         without grandfathering new violations (ISSUE-320).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import check_rules  # noqa: E402


def test_update_baseline_prunes_resolved_not_new(tmp_path: Path) -> None:
    """--update-baseline removes resolved entries but must not grandfather new violations.

    ISSUE-320: the old implementation wrote ``current`` as the new baseline, which
    would silently grandfather any new violation that happened to be present at update
    time.  The fixed implementation prunes only the resolved entries and leaves new
    violations unbaselined so they remain visible as failures.
    """
    baseline_file = tmp_path / "rules_baseline.txt"

    existing = "R006|src/some_module.py::some_function"
    resolved = "R006|src/other_module.py::old_function"
    baseline_file.write_text(f"{existing}\n{resolved}\n", encoding="utf-8")

    new_violation = "R006|src/new_module.py::new_function"
    current = {existing, new_violation}

    result = check_rules._run_check(current, baseline_file, "test", update_flag=True)

    assert result == 0
    updated = check_rules._load_baseline(baseline_file)
    assert resolved not in updated, "resolved entry must be pruned from baseline"
    assert new_violation not in updated, "new violations must not be grandfathered by --update-baseline"
    assert existing in updated, "still-active violation must remain grandfathered"


def test_update_baseline_produces_empty_baseline_when_all_resolved(tmp_path: Path) -> None:
    """When every grandfathered violation is fixed, --update-baseline empties the baseline."""
    baseline_file = tmp_path / "rules_baseline.txt"
    baseline_file.write_text("R006|src/old.py::old_fn\n", encoding="utf-8")

    result = check_rules._run_check(set(), baseline_file, "test", update_flag=True)

    assert result == 0
    assert check_rules._load_baseline(baseline_file) == set()
