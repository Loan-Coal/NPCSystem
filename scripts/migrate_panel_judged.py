"""
Module: migrate_panel_judged
Layer: scripts (ops utility — not part of src/ or the eval harness proper)
Purpose: Convert a legacy panel-mode judged.jsonl — the 6-field shape the
         2026-08-17 overnight run wrote — into the current two-file layout
         (judged.jsonl consensus rows + judged_panel_votes.jsonl seat rows),
         recomputing `passed` with expected_polarity and restoring `repetition`,
         `case_id` and `judge_kind` by joining against the run's own transcript.
Dependencies: argparse, json, pathlib, sys; eval_records, judge_panel,
         judge_panel_runner, judged_persistence, panel_metrics, run_status (evals/)
Used by: operators, once per legacy artifact. Safe to re-run: it reads the
         transcript and the legacy file and writes fresh outputs.

WHY A JOIN IS SOUND HERE
The legacy rows carry no repetition, so the association has to be recovered.
It is recoverable exactly, not guessed: judge_transcript_panel emitted verdicts
in transcript order, len(panel) seats per judge_kind record, contiguously. So
legacy row 3i..3i+2 corresponds to the i-th judge_kind record of the transcript.
verify_alignment() proves that mapping holds for the file it is given — matching
row count, one record_id per group, and each group's record_id equal to its
transcript record's — and refuses to write anything if it does not.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

from eval_records import JudgedRecord, read_transcript  # noqa: E402
from judge_panel import PanelScoredRecord, PanelVerdict, consensus_verdict  # noqa: E402
from judge_panel_runner import _panel_fail_votes  # noqa: E402
from judged_persistence import write_consensus_jsonl, write_seat_votes_jsonl  # noqa: E402
from panel_metrics import compute_panel_metrics  # noqa: E402
from panel_metrics_format import console_lines  # noqa: E402
from run_status import RunStatus, write_run_status  # noqa: E402

_VOTES_FILENAME: str = "judged_panel_votes.jsonl"
_STATUS_FILENAME: str = "run_status.json"
_LEGACY_SUFFIX: str = ".legacy-6field.bak"


class AlignmentError(RuntimeError):
    """Raised when the legacy file cannot be proven to line up with the transcript."""


def _read_legacy(path: Path) -> list[dict]:
    """Load legacy judged rows in file order."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify_alignment(legacy: list[dict], records: list, panel_size: int) -> None:
    """Prove the legacy rows map 1:1 onto transcript records before writing anything.

    Args:
        legacy: Legacy rows in file order.
        records: The transcript's judge_kind records, in transcript order.
        panel_size: Seats per record (rows per group).
    Raises:
        AlignmentError: If counts mismatch, a group spans two record_ids, or a
            group's record_id differs from its transcript record's.
    """
    if len(legacy) != len(records) * panel_size:
        raise AlignmentError(
            f"legacy rows ({len(legacy)}) != records x seats "
            f"({len(records)} x {panel_size} = {len(records) * panel_size})"
        )
    for i, record in enumerate(records):
        group = legacy[i * panel_size:(i + 1) * panel_size]
        ids = {row["record_id"] for row in group}
        if len(ids) != 1:
            raise AlignmentError(f"group {i} spans multiple record_ids: {sorted(ids)}")
        if ids.pop() != record.record_id:
            raise AlignmentError(
                f"group {i} is '{group[0]['record_id']}' but transcript record is "
                f"'{record.record_id}' — file order does not match transcript order"
            )


def _rebuild(legacy: list[dict], records: list, panel_size: int) -> list[PanelScoredRecord]:
    """Pair each transcript record with its seats' raw verdicts."""
    scored = []
    for i, record in enumerate(records):
        group = legacy[i * panel_size:(i + 1) * panel_size]
        scored.append(
            PanelScoredRecord(
                record=record,
                verdicts=tuple(
                    PanelVerdict(
                        record_id=record.record_id,
                        judge_model=row["judge_model"],
                        score=row["score"],
                        error=row.get("error", "") or row.get("detail", ""),
                    )
                    for row in group
                ),
            )
        )
    return scored


def _consensus_records(scored: list[PanelScoredRecord]) -> list[JudgedRecord]:
    """Recompute each record's consensus verdict from its seats' raw scores."""
    out = []
    for item in scored:
        fail_votes = _panel_fail_votes(list(item.verdicts), item.record.expected_polarity)
        consensus_fail, n_available = consensus_verdict(fail_votes)
        passed = not consensus_fail
        out.append(
            JudgedRecord(
                **item.record.model_dump(),
                passed=passed,
                score=passed if n_available > 0 else None,
                reasoning="; ".join(
                    f"{v.judge_model}: {v.error}" for v in item.verdicts if v.error
                ),
            )
        )
    return out


def migrate(gen_dir: Path, *, panel_size: int, dry_run: bool) -> int:
    """Migrate one generation directory's legacy panel judged.jsonl in place.

    Args:
        gen_dir: evals/generations/<gen_id>/ holding outputs.jsonl + judged.jsonl.
        panel_size: Number of panel seats the legacy run used.
        dry_run: Print the corrected metrics without writing any file.
    Returns:
        0 on success, 2 when alignment cannot be proven.
    """
    judged_path = gen_dir / "judged.jsonl"
    transcript = read_transcript(gen_dir / "outputs.jsonl")
    records = [r for r in transcript.records if r.judge_kind is not None]
    legacy = _read_legacy(judged_path)

    try:
        verify_alignment(legacy, records, panel_size)
    except AlignmentError as exc:
        print(f"REFUSING TO MIGRATE: {exc}", file=sys.stderr)
        return 2

    scored = _rebuild(legacy, records, panel_size)
    consensus = _consensus_records(scored)
    metrics = compute_panel_metrics(scored)

    print(f"Alignment verified: {len(legacy)} legacy rows -> {len(records)} records x {panel_size} seats")
    print(f"Consensus: {sum(1 for r in consensus if r.passed)}/{len(consensus)} records passed")
    print("")
    for line in console_lines(metrics):
        print(line)

    if dry_run:
        print("\n(dry run — nothing written)")
        return 0

    backup = judged_path.with_suffix(judged_path.suffix + _LEGACY_SUFFIX)
    if not backup.exists():
        backup.write_text(judged_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"\nLegacy file preserved at {backup}")

    write_consensus_jsonl(consensus, judged_path, panel_size=panel_size)
    write_seat_votes_jsonl(scored, gen_dir / _VOTES_FILENAME)
    passed = sum(1 for r in consensus if r.passed)
    write_run_status(
        RunStatus(
            status="gate_failed" if passed < len(consensus) else "ok",
            cases_passed=passed,
            cases_total=len(consensus),
            judge_panel=tuple(dict.fromkeys(v.judge_model for v in scored[0].verdicts)),
            fleiss_kappa=metrics.kappa.kappa,
            raw_agreement=metrics.agreement.rate,
            votes_path=str(gen_dir / _VOTES_FILENAME),
            provenance=(
                "re-derived from a legacy 6-field panel artifact by "
                "scripts/migrate_panel_judged.py — raw judge scores are the original "
                "2026-08-17 run; passed/repetition/case_id/judge_kind were recovered "
                "by transcript join, not re-judged"
            ),
        ),
        gen_dir / _STATUS_FILENAME,
    )
    print(f"Wrote {judged_path}, {gen_dir / _VOTES_FILENAME}, {gen_dir / _STATUS_FILENAME}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the migration."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[3].strip())
    parser.add_argument("gen_dir", type=Path, help="evals/generations/<gen_id>/")
    parser.add_argument("--panel-size", type=int, default=3, help="Seats the legacy run used.")
    parser.add_argument("--dry-run", action="store_true", help="Print metrics; write nothing.")
    args = parser.parse_args(argv)
    return migrate(args.gen_dir, panel_size=args.panel_size, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
