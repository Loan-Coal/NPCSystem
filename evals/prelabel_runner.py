"""
Module: prelabel_runner
Layer: evals (eval harness — not part of src/)
Purpose: Drive the Opus pre-labelling pass over exported stratified batches and append
         validated 4-key raw label rows — the committed, resumable, provenance-logged
         replacement for the ad-hoc PowerShell loop that was step 3 of
         evals/calibration/README.md (measurement-remediation Phase 5, DEC-272).
Dependencies: argparse, hashlib, json, re, subprocess, sys, datetime, pathlib (stdlib);
              calibration_records (LABELS_FILE), raw_label_rows (RawLabelRow,
              check_contamination) — the same validation the importer applies, applied
              here so a malformed labelling session is caught at write time, not hours
              later at import time
Used by: evals/__main__.py ("prelabel" verb), Makefile prelabel target
Does NOT: import from src/npc_engine/; add an `anthropic` SDK dependency or handle an API
          key (it shells out to the already-installed `claude` CLI, preserving the
          recorded decision to label without adding a dependency); write to
          labels_v1.jsonl (refused outright); or invent a label — every row it writes came
          out of the model it invoked.

Two defects in the loop this replaces, both fixed here and both found by measurement:

1. **The prompt cannot go on argv.** The README loop passed prompt+batch as a command-line
   argument (`claude -p $prompt`). The largest exported batch is 37,420 chars and the Opus
   prompt is 15,565, so the combined 52,985 exceeds Windows' 32,767-char CreateProcess
   limit — the three largest tone_judge batches could not be labelled that way at all.
   This module writes the prompt to the CLI's **stdin** instead, which has no such limit.
2. **The pass left no reproducible trace.** The only record of the previous 354-row run is
   an untracked .log covering 9 of 16 batches, so the pass demonstrably ran in at least two
   uncoordinated invocations. This module is resumable by construction (it skips a batch
   whose rows are already present in the output) and writes a provenance header naming the
   prompt's sha256, the model, and the batch directory.

The `<BATCH>` framing below is the labelling prompt's own input contract — owned by
evals/calibration/OPUS_LABEL_PROMPT.md ("Input format") and mirrored in that directory's
README. The prompt text itself is never inlined here; this module only reproduces the
delimiters, so no prompt string lives in Python (CLAUDE.md's prompts rule).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from calibration_records import LABELS_FILE
from raw_label_rows import ContaminatedRowError, RawLabelRow, check_contamination

DEFAULT_PROMPT_PATH: Path = Path(__file__).resolve().parent / "calibration" / "OPUS_LABEL_PROMPT.md"
DEFAULT_MODEL: str = "opus"
DEFAULT_CLI: str = "claude"
DEFAULT_TIMEOUT_S: float = 900.0

_BATCH_OPEN: str = "<BATCH>"
_BATCH_CLOSE: str = "</BATCH>"

_JSON_LINE = re.compile(r"^\s*\{")
_LEADING_HTML_COMMENT = re.compile(r"\A\s*<!--.*?-->\s*", re.DOTALL)

LabelKey = tuple[str, str]


class PrelabelInvocationError(RuntimeError):
    """Raised when the labelling CLI exits non-zero or cannot be run at all."""


@dataclass(frozen=True)
class BatchOutcome:
    """What one batch produced.

    Attributes:
        batch: Path of the batch file.
        skipped: True when every row was already present in the output (resume).
        written: Rows validated and appended.
        rejected: Reasons for lines that were dropped, one string each.
    """

    batch: Path
    skipped: bool
    written: int
    rejected: tuple[str, ...] = ()


@dataclass(frozen=True)
class PrelabelSummary:
    """Totals across a whole pre-labelling run.

    Attributes:
        outcomes: One BatchOutcome per batch, in run order.
        rows_written: Total validated rows appended across every batch.
        rows_rejected: Total lines dropped as unparseable, contaminated, or invalid.
    """

    outcomes: tuple[BatchOutcome, ...]
    rows_written: int
    rows_rejected: int

    @property
    def batches_run(self) -> int:
        """Batches actually sent to the labeller."""
        return sum(1 for o in self.outcomes if not o.skipped)

    @property
    def batches_skipped(self) -> int:
        """Batches skipped because their rows were already labelled."""
        return sum(1 for o in self.outcomes if o.skipped)


def load_prompt(path: Path) -> str:
    """Read a labelling prompt, dropping a leading HTML comment block if present.

    Both LABEL_PROMPT.md and OPUS_LABEL_PROMPT.md open with an HTML comment holding
    run instructions and a provenance template, and both warn in that very comment that
    anything which is not prompt content becomes something the model may answer instead
    of labelling. OPUS_LABEL_PROMPT.md states outright that only the body after that
    block is piped. Stripping it is therefore the documented behaviour, not a guess.

    Args:
        path: Path to the prompt markdown file.
    Returns:
        The prompt body, comment removed and surrounding whitespace trimmed.
    """
    return _LEADING_HTML_COMMENT.sub("", path.read_text(encoding="utf-8")).strip()


def build_batch_prompt(prompt_text: str, batch_text: str) -> str:
    """Wrap one batch's JSON in the prompt's declared <BATCH> delimiters."""
    return f"{prompt_text}\n\n{_BATCH_OPEN}\n{batch_text}\n{_BATCH_CLOSE}"


def invoke_labeller(prompt: str, *, cli: str, model: str, timeout: float) -> str:
    """Run the labelling CLI over one prompt and return its stdout.

    The prompt goes on stdin, never argv: prompt plus batch runs past 50,000 characters,
    well over the 32,767-char Windows command-line limit (see the module docstring).

    Args:
        prompt: The full prompt, batch included.
        cli: Executable to run (default `claude`).
        model: Model alias or full name passed through to the CLI.
        timeout: Seconds to allow before giving up on the batch.
    Returns:
        The CLI's stdout, verbatim.
    Raises:
        PrelabelInvocationError: On a non-zero exit, a timeout, or a missing executable.
    """
    try:
        proc = subprocess.run(
            [cli, "-p", "--model", model],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise PrelabelInvocationError(f"labelling CLI {cli!r} not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise PrelabelInvocationError(f"{cli} timed out after {timeout:.0f}s") from exc
    if proc.returncode != 0:
        raise PrelabelInvocationError(f"{cli} exited {proc.returncode}: {(proc.stderr or '').strip()[-400:]}")
    return proc.stdout or ""


def parse_response_rows(stdout: str) -> tuple[list[RawLabelRow], list[str]]:
    """Validate a labelling response into raw rows, reporting every dropped line.

    Applies exactly the importer's own checks — the contamination guard first, then
    RawLabelRow's 4-field schema — so a bad session fails here rather than at import.

    Args:
        stdout: The labeller's raw output.
    Returns:
        (validated rows, one rejection reason per dropped line).
    """
    rows: list[RawLabelRow] = []
    rejected: list[str] = []
    for line in stdout.splitlines():
        if not _JSON_LINE.match(line):
            continue
        row, reason = _validate_line(line)
        if row is not None:
            rows.append(row)
        elif reason:
            rejected.append(reason)
    return rows, rejected


def _validate_line(line: str) -> tuple[RawLabelRow | None, str]:
    """Parse and validate one candidate JSONL line; return (row, rejection reason)."""
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        return None, f"unparseable JSON ({exc.msg}): {line[:120]}"
    if not isinstance(payload, dict):
        return None, f"not a JSON object: {line[:120]}"
    try:
        check_contamination(payload, str(payload.get("record_id", "<unknown>")))
        return RawLabelRow.model_validate(payload), ""
    except (ContaminatedRowError, ValueError) as exc:
        return None, f"invalid row {payload.get('record_id', '<unknown>')!r}: {exc}"


def batch_keys(batch_path: Path) -> list[LabelKey]:
    """Read a batch file's (record_id, scorer) keys, in file order."""
    items = json.loads(batch_path.read_text(encoding="utf-8"))
    return [(item["record_id"], item["scorer"]) for item in items if isinstance(item, dict)]


def existing_keys(out_path: Path) -> set[LabelKey]:
    """Every (record_id, scorer) already present in the raw output file.

    Tolerant by design: the output is append-only across resumed runs, so a partially
    written trailing line from an interrupted run must not make the whole file unreadable.
    """
    if not out_path.exists():
        return set()
    keys: set[LabelKey] = set()
    for line in out_path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "record_id" in payload and "scorer" in payload:
            keys.add((payload["record_id"], payload["scorer"]))
    return keys


def append_rows(out_path: Path, rows: Sequence[RawLabelRow]) -> None:
    """Append validated rows as JSONL, UTF-8, LF-terminated."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row.model_dump(), ensure_ascii=False) + "\n")


def _run_one_batch(
    batch: Path,
    out_path: Path,
    done: set[LabelKey],
    *,
    prompt_text: str,
    cli: str,
    model: str,
    timeout: float,
    dry_run: bool,
) -> BatchOutcome:
    """Label one batch unless its rows are already present, appending what validates."""
    keys = batch_keys(batch)
    if keys and all(key in done for key in keys):
        return BatchOutcome(batch=batch, skipped=True, written=0)
    if dry_run:
        return BatchOutcome(batch=batch, skipped=False, written=0)

    prompt = build_batch_prompt(prompt_text, batch.read_text(encoding="utf-8"))
    rows, rejected = parse_response_rows(invoke_labeller(prompt, cli=cli, model=model, timeout=timeout))
    in_batch, strays = _split_by_batch(rows, set(keys))
    rejected.extend(strays)
    fresh = [row for row in in_batch if (row.record_id, row.scorer) not in done]
    append_rows(out_path, fresh)
    done.update((row.record_id, row.scorer) for row in fresh)
    return BatchOutcome(batch=batch, skipped=False, written=len(fresh), rejected=tuple(rejected))


def _split_by_batch(
    rows: Sequence[RawLabelRow], batch_key_set: set[LabelKey]
) -> tuple[list[RawLabelRow], list[str]]:
    """Separate rows belonging to this batch from rows the labeller invented.

    A row whose key is not in the batch it was asked to label is rejected rather than
    written. The failure this guards is documented in the prompt itself: `record_id` must
    be copied verbatim including its `#r<n>` repetition suffix, and a row that drops the
    suffix would be normalised to repetition 0 at import and silently attached to a
    DIFFERENT output than the one that was labelled.

    Args:
        rows: Validated rows from one labelling response.
        batch_key_set: The (record_id, scorer) keys the batch actually contained.
    Returns:
        (rows belonging to the batch, one rejection reason per stray row).
    """
    kept = [row for row in rows if (row.record_id, row.scorer) in batch_key_set]
    strays = [
        f"row {row.record_id!r} is not in this batch (record_id must be copied verbatim, #r suffix included)"
        for row in rows
        if (row.record_id, row.scorer) not in batch_key_set
    ]
    return kept, strays


def run_prelabelling(
    batches: Sequence[Path],
    out_path: Path,
    *,
    prompt_text: str,
    cli: str = DEFAULT_CLI,
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT_S,
    dry_run: bool = False,
    log_fn: Callable[[str], None] = print,
) -> PrelabelSummary:
    """Label every batch in order, skipping any whose rows are already written.

    Args:
        batches: Batch files to label, in the order they should run.
        out_path: Raw-label JSONL to append to; read first to resume.
        prompt_text: Prompt body from load_prompt().
        cli: Labelling CLI executable.
        model: Model alias passed to the CLI.
        timeout: Per-batch timeout in seconds.
        dry_run: Plan only — resolve what would run and invoke nothing.
        log_fn: Progress sink, one line per batch.
    Returns:
        The run summary.
    """
    done = existing_keys(out_path)
    outcomes: list[BatchOutcome] = []
    for batch in batches:
        outcome = _run_one_batch(
            batch, out_path, done,
            prompt_text=prompt_text, cli=cli, model=model, timeout=timeout, dry_run=dry_run,
        )
        outcomes.append(outcome)
        log_fn(_format_outcome(outcome, len(done)))
    return PrelabelSummary(
        outcomes=tuple(outcomes),
        rows_written=sum(o.written for o in outcomes),
        rows_rejected=sum(len(o.rejected) for o in outcomes),
    )


def _format_outcome(outcome: BatchOutcome, cumulative: int) -> str:
    """Render one batch's progress line."""
    if outcome.skipped:
        return f"  {outcome.batch}: skipped (already labelled)"
    tail = f", {len(outcome.rejected)} rejected" if outcome.rejected else ""
    return f"  {outcome.batch}: +{outcome.written} row(s){tail} (cumulative {cumulative})"


def write_provenance_log(log_path: Path, *, prompt_path: Path, batch_dir: Path, model: str, gen_id: str) -> None:
    """Record what this run labelled, with what prompt, against which generation.

    The previous pass left only an untracked partial log, so a stale prompt or a
    mismatched gen_id was undetectable after the fact. This is that record.
    """
    prompt_sha = hashlib.sha256(prompt_path.read_bytes()).hexdigest()[:12]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            f"=== prelabel {datetime.now(timezone.utc).isoformat()} "
            f"gen_id={gen_id or '<unset>'} model={model} "
            f"prompt={prompt_path.name}@{prompt_sha} batches={batch_dir} ===\n"
        )


def _build_parser() -> argparse.ArgumentParser:
    """Build the `prelabel` verb's argument parser."""
    parser = argparse.ArgumentParser(description="Opus pre-labelling pass over exported batches (DEC-272).")
    parser.add_argument("--batch-dir", type=Path, required=True, help="Directory of exported batch_*.json files.")
    parser.add_argument("--out", type=Path, required=True, help="Raw-label JSONL to append to (resumable).")
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT_PATH, help="Labelling prompt markdown.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model alias passed to the CLI.")
    parser.add_argument("--cli", default=DEFAULT_CLI, help="Labelling CLI executable.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="Per-batch timeout, seconds.")
    parser.add_argument("--gen-id", default="", help="Generation id, recorded in the provenance log.")
    parser.add_argument("--limit", type=int, default=0, help="Consider at most N batches this run, skips included (0 = all).")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; invoke nothing.")
    return parser


def _resolve_batches(batch_dir: Path, limit: int) -> list[Path]:
    """Every batch_*.json under batch_dir, sorted, optionally capped."""
    batches = sorted(batch_dir.rglob("batch_*.json"))
    return batches[:limit] if limit > 0 else batches


def main(argv: list[str] | None = None) -> int:
    """Run the pre-labelling pass. Returns 0 on success, 2 on a refused or empty request."""
    args = _build_parser().parse_args(argv)
    if args.out.resolve() == LABELS_FILE.resolve():
        print(f"refusing to write raw rows over the labels artifact: {LABELS_FILE}", file=sys.stderr)
        return 2
    batches = _resolve_batches(args.batch_dir, args.limit)
    if not batches:
        print(f"no batch_*.json found under {args.batch_dir}", file=sys.stderr)
        return 2

    prompt_text = load_prompt(args.prompt)
    if not args.dry_run:
        write_provenance_log(
            args.out.with_suffix(".log"),
            prompt_path=args.prompt, batch_dir=args.batch_dir, model=args.model, gen_id=args.gen_id,
        )
    print(f"{'DRY RUN: ' if args.dry_run else ''}{len(batches)} batch(es) from {args.batch_dir} -> {args.out}")
    summary = run_prelabelling(
        batches, args.out,
        prompt_text=prompt_text, cli=args.cli, model=args.model,
        timeout=args.timeout, dry_run=args.dry_run,
    )
    print(
        f"DONE. {summary.batches_run} run, {summary.batches_skipped} skipped, "
        f"{summary.rows_written} row(s) written, {summary.rows_rejected} rejected."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
