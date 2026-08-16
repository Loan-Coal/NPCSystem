"""
Module: test_drift_trust_policy
Layer: test (unit)
Purpose: RED anchor for EVAL-P20.3b (ISSUE-168 rescope) — evals/label_merge.py's
         _has_drifted must trust a stored human_verdict against real per-token
         sampling variation in k3_73e6c36, the committed generation artifact,
         not a synthetic string. Pins the chosen policy (DEC-181, option (d)):
         drift = criteria_sha256 change only.
Dependencies: pytest, label_merge, calibration_records, content_hash (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

import json
from pathlib import Path

from calibration_records import CalibrationLabel
from content_hash import sha256_text
from label_merge import _has_drifted, merge_labels

_K3_OUTPUTS = (
    Path(__file__).resolve().parents[3]
    / "evals" / "generations" / "k3_73e6c36" / "outputs.jsonl"
)

# Two real repetitions of case_001_grieving_elder:tone_judge:5 — same criteria,
# genuinely different npc_response text (per-token sampling variation, not a
# synthetic diff). Pulled from the committed k3_73e6c36 artifact.
_REAL_CASE_PREFIX = "case_001_grieving_elder:tone_judge:5"


def _load_real_repetition_pair() -> tuple[str, str, str]:
    """Return (criteria, output_text_a, output_text_b) for a real k3_73e6c36 pair.

    Raises:
        AssertionError: If the committed artifact no longer contains a
            repetition pair for _REAL_CASE_PREFIX with matching criteria and
            differing output text — this test must fail loudly, not silently
            fall back to a synthetic fixture, per the roadmap's own
            "not a synthetic string" requirement.
    """
    rows = [
        json.loads(line)
        for line in _K3_OUTPUTS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matches = [r for r in rows if r["record_id"].startswith(_REAL_CASE_PREFIX)]
    texts = {r["npc_response"] for r in matches}
    criterias = {r["criteria"] for r in matches}
    assert len(criterias) == 1, "expected one stable criteria across repetitions"
    assert len(texts) >= 2, "expected genuinely differing output text across repetitions"
    ordered_texts = sorted(texts)
    return next(iter(criterias)), ordered_texts[0], ordered_texts[1]


def _label(**overrides: object) -> CalibrationLabel:
    base: dict[str, object] = dict(
        record_id=f"{_REAL_CASE_PREFIX}#r0",
        scorer="tone_judge",
        output_text="",
        scorer_verdict=True,
        pre_label=True,
        pre_labeller_model="claude-opus-5",
        human_verdict=True,
        adjudicated_at="2026-08-01T00:00:00+00:00",
        notes="",
        criteria="",
        player_message="",
        observed={},
        output_sha256="",
        criteria_sha256="",
    )
    base.update(overrides)
    return CalibrationLabel(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_real_k3_repetition_pair_survives_as_not_drifted() -> None:
    """A real k3_73e6c36 repetition pair with identical criteria is trusted.

    RED anchor for EVAL-P20.3b: before the fix, _has_drifted also compared
    output_sha256, so this real sampling-variation pair (same criteria,
    different text — exactly the population DEC-176 measured at 4.2% byte-
    identical reproduction) would have been flagged needs_review despite the
    scorer's criteria never changing.
    """
    criteria, text_a, text_b = _load_real_repetition_pair()
    assert text_a != text_b  # confirms this is a genuine sampling-variation pair

    criteria_hash = sha256_text(criteria)
    existing = _label(
        output_text=text_a,
        criteria=criteria,
        output_sha256=sha256_text(text_a),
        criteria_sha256=criteria_hash,
        human_verdict=True,
    )
    incoming = _label(
        output_text=text_b,
        criteria=criteria,
        output_sha256=sha256_text(text_b),
        criteria_sha256=criteria_hash,
    )
    assert _has_drifted(existing, incoming) is False

    result = merge_labels([existing], [incoming])
    merged = result.rows[0]
    assert merged.needs_review is False
    assert merged.human_verdict is True  # the stored human verdict survives
    assert merged.output_text == text_b  # output_text still refreshes (audit trail)


def test_real_k3_pair_with_perturbed_criteria_still_drifts() -> None:
    """The same real text pair DOES drift if the criteria itself changes.

    Confirms the new policy isn't a no-op — it still catches the one signal
    it's defined to catch.
    """
    criteria, text_a, text_b = _load_real_repetition_pair()
    existing = _label(
        output_text=text_a,
        criteria=criteria,
        output_sha256=sha256_text(text_a),
        criteria_sha256=sha256_text(criteria),
        human_verdict=True,
    )
    incoming = _label(
        output_text=text_b,
        criteria=criteria + " (revised)",
        output_sha256=sha256_text(text_b),
        criteria_sha256=sha256_text(criteria + " (revised)"),
    )
    assert _has_drifted(existing, incoming) is True
