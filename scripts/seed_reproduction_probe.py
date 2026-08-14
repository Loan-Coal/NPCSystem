"""
Module: seed_reproduction_probe
Layer: harness (eval tooling — imports evals/, never src/)
Purpose: Measure what fraction of npc_response text two same-seed generation runs
    reproduce byte-for-byte, which is EVAL-P20.0's >=95% gate (HUMAN GATE H4).
Dependencies: stdlib argparse/json/pathlib/sys/datetime; pydantic; evals/ `eval_records`
    and `record_identity`.
Used by: `make seed-probe`, tests/unit/scripts/test_seed_reproduction_probe.py.

Why this exists as committed code rather than an ad-hoc script: the 19.0% no-seed
baseline this gate is measured against was computed by hand and never checked in, so it
cannot be re-derived today. A claim that blocks two regenerations and ~660 potential
re-adjudications has to be reproducible. See DEC-176.

Reports two rates deliberately (see DEC-176):
  rate_records — identical / total records; the roadmap's literal wording.
  rate_calls   — identical / distinct (case, repetition) pairs; the number of independent
                 LLM draws. Guard cases emit ~6 records per case per repetition, so one
                 drifting response moves rate_records by ~1/6 of what it moves rate_calls.
                 Gating on rate_records would overstate precision ~6x, so the gate is
                 rate_calls and both are recorded.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "evals"))

from eval_records import GenerationRecord, read_transcript  # noqa: E402
from record_identity import composite_item_id  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: EVAL-P20.0's gate. Below this the seed did not solve label survival and the
#: programme must fall back to the explicit-relabel branch — never proceed on hope.
REPRODUCTION_GATE: float = 0.95

#: Separator between the case id and the rest of a record_id ('<case>:<kind>:<index>').
_RECORD_ID_SEPARATOR: str = ":"

#: How many divergent items to show, and how much of each side. If the gate fails the
#: immediate next question is "differing how", so a bare rate is not enough.
_MAX_DIVERGENCE_SAMPLES: int = 3
_DIVERGENCE_EXCERPT_CHARS: int = 200

_DEFAULT_GENERATIONS_DIR: Path = _REPO_ROOT / "evals" / "generations"
_DEFAULT_JSON_OUT: Path = _REPO_ROOT / "evals" / "seed_reproduction.json"

_VERDICT_MET: str = "MET"
_VERDICT_NOT_MET: str = "NOT_MET"

_EXIT_OK: int = 0
_EXIT_GATE_FAILED: int = 1
_EXIT_INCOMPARABLE: int = 2


class SeedReproductionError(RuntimeError):
    """Raised when the two runs cannot be compared at all."""


class SeedReproductionRecord(BaseModel):
    """Committed measurement record for one seed-reproduction comparison.

    Attributes:
        rate_records: Byte-identical npc_response fraction over all records.
        rate_calls: The same over distinct (case, repetition) pairs — the gated number.
        n_records: Total records compared.
        n_calls: Total independent LLM draws compared.
        identical_records: Count of byte-identical records.
        identical_calls: Count of draws where every record matched.
        seed: The seed both runs ran at, read from run A's config block.
        gen_id_a: Generation id of the first run.
        gen_id_b: Generation id of the second run.
        generation_model: Model tag both runs used.
        generation_model_digest: Ollama content digest, so a later divergence caused by a
            re-pulled model is diagnosable rather than mysterious.
        ollama_version: Ollama server version string.
        git_sha: Commit both runs were generated at.
        gate: The threshold rate_calls was judged against.
        verdict: MET or NOT_MET.
        measured_at: UTC ISO-8601 timestamp.
    """

    model_config = ConfigDict(frozen=True)

    rate_records: float
    rate_calls: float
    n_records: int
    n_calls: int
    identical_records: int
    identical_calls: int
    seed: int | None
    gen_id_a: str
    gen_id_b: str
    generation_model: str
    generation_model_digest: str | None
    ollama_version: str | None
    git_sha: str
    gate: float
    verdict: str
    measured_at: str


def _resolve_gen_dir(name: str, generations_dir: Path) -> Path:
    """Resolve a gen_id or path to a generation directory's outputs.jsonl."""
    candidate = Path(name)
    gen_dir = candidate if candidate.is_dir() else generations_dir / name
    outputs = gen_dir / "outputs.jsonl"
    if not outputs.exists():
        raise SeedReproductionError(f"no outputs.jsonl under {gen_dir}")
    return outputs


def _index_by_item_id(records: Sequence[GenerationRecord]) -> dict[str, GenerationRecord]:
    """Key records by composite item id — the same join key labels use."""
    return {composite_item_id(r.record_id, r.repetition): r for r in records}


def _call_key(item_id: str) -> tuple[str, str]:
    """Group an item id by independent LLM draw: (case id, repetition suffix)."""
    record_id, _, repetition = item_id.rpartition("#")
    case = record_id.split(_RECORD_ID_SEPARATOR)[0]
    return case, repetition


def _compare(
    a: dict[str, GenerationRecord], b: dict[str, GenerationRecord]
) -> tuple[dict[str, bool], list[str]]:
    """Return per-item identity flags and the ids whose text diverged.

    Raises:
        SeedReproductionError: If the two runs do not cover the same item ids. A silently
            shrunken denominator is the exact defect that shipped EVAL-P8.2's
            "Intersection: 0 cases / p=1.0000 / exit 0", so this refuses rather than
            intersecting.
    """
    only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    if only_a or only_b:
        raise SeedReproductionError(
            f"runs do not cover the same items; only in A: {only_a[:5]} "
            f"({len(only_a)} total), only in B: {only_b[:5]} ({len(only_b)} total)"
        )
    flags = {item_id: a[item_id].npc_response == b[item_id].npc_response for item_id in a}
    return flags, [item_id for item_id, same in flags.items() if not same]


def _rate(numerator: int, denominator: int) -> float:
    """Fraction, or 0.0 for an empty denominator — never a silent 100%."""
    return numerator / denominator if denominator else 0.0


def _call_level(flags: dict[str, bool]) -> tuple[int, int]:
    """Collapse per-record flags to per-draw: a draw counts only if every record matched."""
    per_call: dict[tuple[str, str], bool] = {}
    for item_id, same in flags.items():
        key = _call_key(item_id)
        per_call[key] = per_call.get(key, True) and same
    return sum(per_call.values()), len(per_call)


def measure(outputs_a: Path, outputs_b: Path) -> tuple[SeedReproductionRecord, list[str]]:
    """Compare two generation dirs and return the measurement plus divergent item ids.

    Args:
        outputs_a: Path to run A's outputs.jsonl.
        outputs_b: Path to run B's outputs.jsonl.
    Returns:
        (record, divergent item ids).
    Raises:
        SeedReproductionError: If the runs cover different items or ran at different seeds.
    """
    transcript_a, transcript_b = read_transcript(outputs_a), read_transcript(outputs_b)
    config_a, config_b = transcript_a.config, transcript_b.config
    seed_a = config_a.seed if config_a is not None else None
    seed_b = config_b.seed if config_b is not None else None
    if seed_a != seed_b:
        raise SeedReproductionError(f"runs used different seeds: A={seed_a!r} B={seed_b!r}")

    flags, divergent = _compare(
        _index_by_item_id(transcript_a.records), _index_by_item_id(transcript_b.records)
    )
    identical_records, n_records = sum(flags.values()), len(flags)
    identical_calls, n_calls = _call_level(flags)
    rate_calls = _rate(identical_calls, n_calls)
    record = SeedReproductionRecord(
        rate_records=_rate(identical_records, n_records),
        rate_calls=rate_calls,
        n_records=n_records,
        n_calls=n_calls,
        identical_records=identical_records,
        identical_calls=identical_calls,
        seed=seed_a,
        gen_id_a=transcript_a.gen_id,
        gen_id_b=transcript_b.gen_id,
        generation_model=config_a.generation_model if config_a else "",
        generation_model_digest=config_a.generation_model_digest if config_a else None,
        ollama_version=config_a.ollama_version if config_a else None,
        git_sha=config_a.git_sha if config_a else "",
        gate=REPRODUCTION_GATE,
        verdict=_VERDICT_MET if rate_calls >= REPRODUCTION_GATE else _VERDICT_NOT_MET,
        measured_at=datetime.now(timezone.utc).isoformat(),
    )
    return record, divergent


def _print_divergences(
    divergent: Sequence[str], outputs_a: Path, outputs_b: Path
) -> None:
    """Show the first few divergent items side by side."""
    a = _index_by_item_id(read_transcript(outputs_a).records)
    b = _index_by_item_id(read_transcript(outputs_b).records)
    print(f"\nDivergent items ({len(divergent)} total, showing {_MAX_DIVERGENCE_SAMPLES}):")
    for item_id in divergent[:_MAX_DIVERGENCE_SAMPLES]:
        print(f"  {item_id}")
        print(f"    A: {a[item_id].npc_response[:_DIVERGENCE_EXCERPT_CHARS]!r}")
        print(f"    B: {b[item_id].npc_response[:_DIVERGENCE_EXCERPT_CHARS]!r}")


def _report(record: SeedReproductionRecord) -> None:
    """Print the measurement in the form the roadmap entry quotes."""
    print(f"seed:            {record.seed}")
    print(f"gen_ids:         {record.gen_id_a} vs {record.gen_id_b}")
    print(f"model:           {record.generation_model} ({record.generation_model_digest})")
    print(f"ollama:          {record.ollama_version}")
    print(f"rate_records:    {record.rate_records:.4f}  ({record.identical_records}/{record.n_records})")
    print(f"rate_calls:      {record.rate_calls:.4f}  ({record.identical_calls}/{record.n_calls})  <- GATED")
    print(f"gate:            >={record.gate}")
    print(f"verdict:         {record.verdict}")


def main(argv: list[str] | None = None) -> int:
    """Measure seed reproduction between two generation dirs.

    Returns:
        0 when the gate is met, 1 when it is not, 2 when the runs are incomparable.
    """
    parser = argparse.ArgumentParser(description="EVAL-P20.0 seed reproduction probe")
    parser.add_argument("--a", required=True, help="gen_id or path of the first run")
    parser.add_argument("--b", required=True, help="gen_id or path of the second run")
    parser.add_argument("--generations-dir", default=_DEFAULT_GENERATIONS_DIR, type=Path)
    parser.add_argument("--json-out", default=_DEFAULT_JSON_OUT, type=Path)
    args = parser.parse_args(argv)

    try:
        outputs_a = _resolve_gen_dir(args.a, args.generations_dir)
        outputs_b = _resolve_gen_dir(args.b, args.generations_dir)
        record, divergent = measure(outputs_a, outputs_b)
    except SeedReproductionError as error:
        print(f"INCOMPARABLE: {error}")
        return _EXIT_INCOMPARABLE

    _report(record)
    if divergent:
        _print_divergences(divergent, outputs_a, outputs_b)
    args.json_out.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {args.json_out}")
    return _EXIT_OK if record.verdict == _VERDICT_MET else _EXIT_GATE_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
