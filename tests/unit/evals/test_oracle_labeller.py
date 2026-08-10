"""
Module: test_oracle_labeller
Layer: test (unit)
Purpose: Unit tests for scripts/oracle_labeller.py — the rule-based labeller whose
         confusion matrix is known by construction, so the export → import →
         adjudicate → calibrate chain can be checked against a number computed
         by hand rather than against itself.
Dependencies: json, pathlib, sys, pytest, oracle_labeller (scripts/)
Used by: pytest (make test / make check)

⚠️ This file must import NOTHING from `evals/calibration*`. The expected kappa is a
hardcoded decimal literal with its arithmetic in a comment, and the matrix is
re-tallied here from the emitted rows. Importing `calibration._kappa_from_matrix`
would validate that function against itself — it returns 1.0 at Pe==1 today
(verified 2026-08-10), which EVAL-P16.3 is scheduled to fix, and this test must
not depend on whether it has.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from oracle_labeller import (  # noqa: E402
    ORACLE_BATCH_DIR,
    ORACLE_LABELS_FILE,
    ORACLE_MODEL_ID,
    MatrixCaps,
    RequestedMatrix,
    UnsatisfiableMatrixError,
    matrix_caps,
    oracle_rows,
)

# ---------------------------------------------------------------------------
# Reference matrix — the satisfiable one from EVAL-P15.1
# ---------------------------------------------------------------------------
#
# refusal_judge on the committed artifact has 68 scorer_verdict=True rows and 7
# scorer_verdict=False rows (n=75, measured 2026-08-10). The naive example from
# an earlier draft (tp=40, fp=5, fn=3, tn=12) needs 15 negatives and is
# unsatisfiable for EVERY scorer in the set. This one saturates all 75 rows
# exactly, with zero slack: tp+fp = 68 positives, fn+tn = 7 negatives.

SCORER: str = "refusal_judge"
POSITIVES_AVAILABLE: int = 68
NEGATIVES_AVAILABLE: int = 7

REFERENCE_TP: int = 60
REFERENCE_FP: int = 8
REFERENCE_FN: int = 4
REFERENCE_TN: int = 3

# Cohen's kappa for (tp=60, fp=8, fn=4, tn=3), computed by hand:
#   n  = 60 + 8 + 4 + 3                       = 75
#   po = (tp + tn) / n        = 63 / 75       = 0.84
#   p_yes_scorer = (tp + fp) / n = 68 / 75
#   p_yes_human  = (tp + fn) / n = 64 / 75
#   p_no_scorer  = (fn + tn) / n =  7 / 75
#   p_no_human   = (fp + tn) / n = 11 / 75
#   pe = (68 * 64 + 7 * 11) / 75**2 = (4352 + 77) / 5625 = 4429 / 5625
#   kappa = (po - pe) / (1 - pe)
#         = (4725 - 4429) / (5625 - 4429)
#         = 296 / 1196
#         = 0.24749163879598662...
EXPECTED_KAPPA: float = 0.247

_KAPPA_DECIMAL_PLACES: int = 3


def _kappa(tp: int, fp: int, fn: int, tn: int) -> float:
    """Cohen's kappa, re-implemented locally so the test never imports the code it checks."""
    n = tp + fp + fn + tn
    po = (tp + tn) / n
    pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
    return (po - pe) / (1.0 - pe)


# ---------------------------------------------------------------------------
# Fixtures — a synthetic export batch dir and judged file
# ---------------------------------------------------------------------------


def _item_id(index: int) -> str:
    return f"case_{index:03d}_synthetic:{SCORER}:0#r0"


@pytest.fixture
def artifact(tmp_path: Path) -> tuple[Path, Path]:
    """Write a batch dir and a judged file with 68 passing and 7 failing rows."""
    batch_dir = tmp_path / "oracle_batches"
    batch_dir.mkdir()

    items: list[dict[str, object]] = []
    judged: list[dict[str, object]] = []
    for i in range(POSITIVES_AVAILABLE + NEGATIVES_AVAILABLE):
        passed = i < POSITIVES_AVAILABLE
        items.append({"record_id": _item_id(i), "scorer": SCORER, "npc_id": "vw_elder"})
        judged.append(
            {"record_id": f"case_{i:03d}_synthetic:{SCORER}:0", "repetition": 0, "passed": passed}
        )
    # A second scorer that must be ignored entirely.
    items.append({"record_id": "case_999_other:tone_judge:0#r0", "scorer": "tone_judge"})
    judged.append({"record_id": "case_999_other:tone_judge:0", "repetition": 0, "passed": True})

    (batch_dir / "batch_001.json").write_text(json.dumps(items), encoding="utf-8")
    judged_path = tmp_path / "judged.jsonl"
    judged_path.write_text(
        "\n".join(json.dumps(row) for row in judged), encoding="utf-8"
    )
    return batch_dir, judged_path


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_emitted_labels_reproduce_the_requested_matrix(artifact: tuple[Path, Path]) -> None:
    batch_dir, judged_path = artifact
    requested = RequestedMatrix(
        tp=REFERENCE_TP, fp=REFERENCE_FP, fn=REFERENCE_FN, tn=REFERENCE_TN
    )

    rows = oracle_rows(batch_dir, [judged_path], SCORER, requested)

    verdicts = {
        f"{json.loads(line)['record_id']}#r{json.loads(line)['repetition']}": json.loads(line)["passed"]
        for line in judged_path.read_text(encoding="utf-8").splitlines()
    }
    tp = sum(1 for r in rows if verdicts[r["record_id"]] and r["pre_label"])
    fp = sum(1 for r in rows if verdicts[r["record_id"]] and not r["pre_label"])
    fn = sum(1 for r in rows if not verdicts[r["record_id"]] and r["pre_label"])
    tn = sum(1 for r in rows if not verdicts[r["record_id"]] and not r["pre_label"])

    assert (tp, fp, fn, tn) == (REFERENCE_TP, REFERENCE_FP, REFERENCE_FN, REFERENCE_TN)


def test_expected_kappa_for_the_reference_matrix_is_the_hardcoded_literal() -> None:
    """The literal above is the value `calibrate` must report to 3 dp."""
    assert round(_kappa(REFERENCE_TP, REFERENCE_FP, REFERENCE_FN, REFERENCE_TN),
                 _KAPPA_DECIMAL_PLACES) == EXPECTED_KAPPA


# ---------------------------------------------------------------------------
# Feasibility: per-cell caps and the named error
# ---------------------------------------------------------------------------


def test_caps_report_the_rows_that_actually_exist(artifact: tuple[Path, Path]) -> None:
    batch_dir, judged_path = artifact
    caps = matrix_caps(batch_dir, [judged_path], SCORER)
    assert caps == MatrixCaps(
        scorer=SCORER,
        positives_available=POSITIVES_AVAILABLE,
        negatives_available=NEGATIVES_AVAILABLE,
    )


def test_the_naive_example_is_rejected_and_the_caps_are_named(artifact: tuple[Path, Path]) -> None:
    """(tp=40, fp=5, fn=3, tn=12) needs 15 negatives; only 7 exist."""
    batch_dir, judged_path = artifact
    requested = RequestedMatrix(tp=40, fp=5, fn=3, tn=12)

    with pytest.raises(UnsatisfiableMatrixError) as excinfo:
        oracle_rows(batch_dir, [judged_path], SCORER, requested)

    message = str(excinfo.value)
    assert "15" in message, "the requested negative count must be named"
    assert str(NEGATIVES_AVAILABLE) in message, "the available negative count must be named"
    assert SCORER in message


def test_too_many_positives_is_also_rejected(artifact: tuple[Path, Path]) -> None:
    batch_dir, judged_path = artifact
    requested = RequestedMatrix(tp=POSITIVES_AVAILABLE, fp=1, fn=1, tn=1)
    with pytest.raises(UnsatisfiableMatrixError):
        oracle_rows(batch_dir, [judged_path], SCORER, requested)


def test_an_unknown_scorer_raises_rather_than_emitting_nothing(artifact: tuple[Path, Path]) -> None:
    """A silent empty emission would look like a completed pass with no labels."""
    batch_dir, judged_path = artifact
    with pytest.raises(UnsatisfiableMatrixError):
        oracle_rows(batch_dir, [judged_path], "no_such_scorer", RequestedMatrix(tp=1, fp=0, fn=0, tn=0))


# ---------------------------------------------------------------------------
# Emission properties
# ---------------------------------------------------------------------------


def test_rows_outside_the_requested_matrix_are_not_emitted(artifact: tuple[Path, Path]) -> None:
    """Leftover rows must be dropped, or they would perturb the known matrix."""
    batch_dir, judged_path = artifact
    requested = RequestedMatrix(tp=10, fp=2, fn=1, tn=1)
    rows = oracle_rows(batch_dir, [judged_path], SCORER, requested)
    assert len(rows) == 14


def test_only_the_target_scorer_is_emitted(artifact: tuple[Path, Path]) -> None:
    batch_dir, judged_path = artifact
    rows = oracle_rows(batch_dir, [judged_path], SCORER, RequestedMatrix(tp=5, fp=1, fn=1, tn=1))
    assert {r["scorer"] for r in rows} == {SCORER}


def test_emission_is_deterministic(artifact: tuple[Path, Path]) -> None:
    """No RNG anywhere — the declared rule must give byte-identical output."""
    batch_dir, judged_path = artifact
    requested = RequestedMatrix(tp=12, fp=3, fn=2, tn=2)
    first = oracle_rows(batch_dir, [judged_path], SCORER, requested)
    second = oracle_rows(batch_dir, [judged_path], SCORER, requested)
    assert first == second


def test_emitted_rows_carry_no_contaminating_fields(artifact: tuple[Path, Path]) -> None:
    batch_dir, judged_path = artifact
    rows = oracle_rows(batch_dir, [judged_path], SCORER, RequestedMatrix(tp=5, fp=1, fn=1, tn=1))
    for row in rows:
        assert set(row) == {"record_id", "scorer", "pre_label", "notes"}


# ---------------------------------------------------------------------------
# The irreversible-loss guard, asserted without importing evals/calibration*
# ---------------------------------------------------------------------------

# Hardcoded rather than imported from calibration_records: this assertion must
# hold against the literal path on disk even if that constant is edited.
_REAL_LABELS_FILE_PARTS: tuple[str, ...] = ("evals", "calibration", "labels_v1.jsonl")


def test_the_oracle_output_path_can_never_equal_the_real_labels_file() -> None:
    assert ORACLE_LABELS_FILE.parts[-3:] != _REAL_LABELS_FILE_PARTS
    assert ORACLE_LABELS_FILE.name != "labels_v1.jsonl"
    assert ORACLE_LABELS_FILE.parts[-3:] == ("calibration", "oracle", "labels_oracle.jsonl")
    assert ORACLE_BATCH_DIR.parts[-2:] == ("calibration", "oracle_batches")


def test_the_oracle_model_id_carries_the_guarded_synthetic_prefix() -> None:
    """The label_import guard keys off this prefix; without it the guard is bypassed."""
    assert ORACLE_MODEL_ID.startswith("oracle-")
