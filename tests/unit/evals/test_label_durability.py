"""
Tests for calibration-label durability: a re-import must never destroy a human
verdict, duplicate keys must be rejected, and criteria drift must be detected
rather than silently re-pointing a human judgment at a different question.

Motivating incident (2026-08-09 audit): the documented `make label-import`
command in evals/calibration/README.md overwrote labels_v1.jsonl with
human_verdict=None on every row, destroying 393 hand-labelled verdicts, and
`--append` produced duplicate keys whose re-adjudication silently overwrote the
original row. Both paths were untested.

Drift definition updated 2026-08-16 (EVAL-P20.3b / DEC-181): drift is now
criteria-only, not output_text — see
test_merge_no_longer_flags_output_drift_alone_eval_p20_3b's docstring and
docs/EVAL_METHODOLOGY.md §3 for the full rationale and the risk this
deliberately accepts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from calibration_records import (
    CalibrationLabel,
    DuplicateLabelKeyError,
    read_calibration_labels,
    write_calibration_labels,
)
from content_hash import sha256_text
from label_merge import merge_labels


def _label(
    record_id: str = "case_a:tone_judge:0#r0",
    *,
    scorer: str = "tone_judge",
    output_text: str = "hello",
    criteria: str = "be nice",
    scorer_verdict: bool = True,
    pre_label: bool = True,
    human_verdict: bool | None = None,
    adjudicated_at: str | None = None,
    notes: str = "",
    needs_review: bool = False,
) -> CalibrationLabel:
    """Build a CalibrationLabel with content hashes derived from its own text."""
    return CalibrationLabel(
        record_id=record_id,
        scorer=scorer,
        output_text=output_text,
        scorer_verdict=scorer_verdict,
        pre_label=pre_label,
        pre_labeller_model="human-lohann",
        human_verdict=human_verdict,
        adjudicated_at=adjudicated_at,
        notes=notes,
        criteria=criteria,
        player_message="hi",
        observed={},
        gen_id="k3_test",
        golden_set_version="deadbeef",
        output_sha256=sha256_text(output_text),
        criteria_sha256=sha256_text(criteria),
        needs_review=needs_review,
    )


# ---------------------------------------------------------------------------
# The core guarantee: a re-import never destroys a human verdict
# ---------------------------------------------------------------------------


def test_merge_preserves_human_verdict_while_refreshing_scorer_verdict() -> None:
    """The exact operation needed after fixing a judge's criteria.

    Re-running the judge produces a new scorer_verdict for the same output.
    The human's judgment of that output is unchanged and must survive.
    """
    adjudicated = _label(
        scorer_verdict=True,
        human_verdict=False,
        adjudicated_at="2026-08-09T11:51:30Z",
        notes="affirms the false premise",
    )
    reimported = _label(scorer_verdict=False)  # judge fixed; verdict flipped

    result = merge_labels((adjudicated,), (reimported,))

    assert len(result.rows) == 1
    merged = result.rows[0]
    assert merged.human_verdict is False, "human verdict must survive re-import"
    assert merged.adjudicated_at == "2026-08-09T11:51:30Z"
    assert merged.notes == "affirms the false premise"
    assert merged.scorer_verdict is False, "scorer verdict must be refreshed"
    assert result.preserved == 1


def test_merge_adds_new_rows_and_reports_counts() -> None:
    existing = _label(record_id="case_a:tone_judge:0#r0", human_verdict=True)
    same = _label(record_id="case_a:tone_judge:0#r0")
    fresh = _label(record_id="case_b:tone_judge:0#r0")

    result = merge_labels((existing,), (same, fresh))

    assert len(result.rows) == 2
    assert result.added == 1
    assert result.preserved == 1


def test_merge_no_longer_flags_output_drift_alone_eval_p20_3b() -> None:
    """SUPERSEDED 2026-08-16 (EVAL-P20.3b / DEC-181, AskUserQuestion option (d)).

    This test used to be named test_merge_flags_output_drift_instead_of_
    silently_rebinding and asserted needs_review=True here — the original
    "motivating incident" guarantee: an output_text change under an existing
    human_verdict must never be silently re-pointed at different text.

    DEC-176 measured byte-identical reproduction as low as 4.2% at the
    shipped max_tokens=512 — that guarantee, applied literally, invalidated
    ~295 rows on every regeneration regardless of whether the underlying
    answer changed in any way a human would call substantive. A human,
    presented with that tradeoff via AskUserQuestion and DEC-176's evidence,
    chose to redefine trust as criteria-only (docs/EVAL_METHODOLOGY.md §3):
    a human_verdict now means "a human judged how this criteria applies to
    this case", not "a human read this exact text". This test intentionally
    now asserts the opposite of what it asserted before that decision — this
    is not a silent regression, it is the redefinition applied consistently.

    The risk this test used to guard against is real and was named explicitly
    to the human before the decision was made (Q3, EVAL-P20-P24 session):
    an output_text that changes to something substantively different (not
    just a paraphrase) under an unchanged criteria now keeps its old verdict
    with no drift signal at all. What still bounds that risk: the live
    anti-hallucination guard/capability rate (summary.py) scores every run's
    *current* text fresh via matchers.py on every call, independent of any
    stored human_verdict — a stale-trusted verdict can only degrade the
    calibration/kappa signal, never let an actual hallucination through the
    safety gate unflagged. See test_merge_flags_criteria_drift below for the
    signal EVAL-P20.3b keeps.
    """
    adjudicated = _label(output_text="the war has ended", human_verdict=False)
    regenerated = _label(output_text="I could not say, stranger")

    result = merge_labels((adjudicated,), (regenerated,))

    merged = result.rows[0]
    assert merged.needs_review is False
    assert merged.human_verdict is False, "verdict survives, now trusted by design"
    assert merged.record_id not in result.drifted


def test_merge_flags_criteria_drift() -> None:
    """Rewriting criteria changes the question the human answered."""
    adjudicated = _label(criteria="be nice", human_verdict=True)
    recriteria = _label(criteria="did the NPC disclose a specific fact?")

    result = merge_labels((adjudicated,), (recriteria,))

    assert result.rows[0].needs_review is True
    assert result.rows[0].record_id in result.drifted


def test_merge_reports_orphans_and_keeps_them() -> None:
    """A label whose record vanished from the transcript must be named, not dropped."""
    orphan = _label(record_id="case_gone:tone_judge:0#r0", human_verdict=True)
    present = _label(record_id="case_a:tone_judge:0#r0")

    result = merge_labels((orphan, present), (present,))

    assert "case_gone:tone_judge:0#r0" in result.orphaned
    assert len(result.rows) == 2, "orphaned human work is retained, not silently lost"


def test_merge_matches_on_scorer_as_well_as_record_id() -> None:
    """Two scorers can share a record_id; they must not collide."""
    tone = _label(scorer="tone_judge", human_verdict=True)
    affirms = _label(scorer="affirms_judge", human_verdict=False)

    result = merge_labels((tone, affirms), (tone, affirms))

    assert len(result.rows) == 2
    verdicts = {(r.scorer, r.human_verdict) for r in result.rows}
    assert verdicts == {("tone_judge", True), ("affirms_judge", False)}


# ---------------------------------------------------------------------------
# Duplicate keys must be impossible to survive
# ---------------------------------------------------------------------------


def test_duplicate_keys_are_rejected_on_read(tmp_path: Path) -> None:
    """--append created 393 duplicate keys; adjudicating one silently overwrote
    the other. Reading such a file must fail loudly instead."""
    path = tmp_path / "labels.jsonl"
    dup = _label(human_verdict=True)
    write_calibration_labels(path, [dup, dup])

    with pytest.raises(DuplicateLabelKeyError, match="case_a:tone_judge:0#r0"):
        read_calibration_labels(path)


def test_merge_rejects_duplicate_keys_in_incoming() -> None:
    row = _label()
    with pytest.raises(DuplicateLabelKeyError):
        merge_labels((), (row, row))


# ---------------------------------------------------------------------------
# File-level durability
# ---------------------------------------------------------------------------


def test_write_ends_with_newline(tmp_path: Path) -> None:
    """Without a trailing newline, `wc -l` under-reports and any append
    concatenates onto the last record."""
    path = tmp_path / "labels.jsonl"
    write_calibration_labels(path, [_label()])

    assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_backs_up_existing_file_holding_human_verdicts(tmp_path: Path) -> None:
    """A rewrite of a file containing human work must leave a recoverable copy."""
    path = tmp_path / "labels.jsonl"
    write_calibration_labels(path, [_label(human_verdict=True)])
    write_calibration_labels(path, [_label(human_verdict=None)])

    backups = list(tmp_path.glob("labels.jsonl.*.bak"))
    assert backups, "expected a .bak beside the rewritten file"
    recovered = read_calibration_labels(backups[0])
    assert recovered[0].human_verdict is True


def test_round_trip_preserves_new_provenance_fields(tmp_path: Path) -> None:
    path = tmp_path / "labels.jsonl"
    original = _label(human_verdict=True, needs_review=True)
    write_calibration_labels(path, [original])

    loaded = read_calibration_labels(path)[0]
    assert loaded.gen_id == "k3_test"
    assert loaded.golden_set_version == "deadbeef"
    assert loaded.output_sha256 == sha256_text("hello")
    assert loaded.criteria_sha256 == sha256_text("be nice")
    assert loaded.needs_review is True


def test_rows_written_before_provenance_fields_existed_still_load(
    tmp_path: Path,
) -> None:
    """Backward compatibility: the 393 committed rows predate these fields."""
    path = tmp_path / "legacy.jsonl"
    path.write_text(
        '{"record_id":"case_a:tone_judge:0#r0","scorer":"tone_judge",'
        '"output_text":"hello","scorer_verdict":true,"pre_label":true,'
        '"pre_labeller_model":"human-lohann","human_verdict":true,'
        '"adjudicated_at":"2026-08-09T11:51:30Z","notes":"",'
        '"criteria":"be nice","player_message":"hi","observed":{}}\n',
        encoding="utf-8",
    )

    loaded = read_calibration_labels(path)

    assert len(loaded) == 1
    assert loaded[0].human_verdict is True
    assert loaded[0].gen_id == ""
    assert loaded[0].needs_review is False
