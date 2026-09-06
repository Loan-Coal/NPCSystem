"""
Module: trend_row_builder
Layer: evals (eval harness — not part of src/)
Purpose: Assemble one TrendRow from a completed run's on-disk artifacts — the
         published rates, the calibration kappas, the panel's agreement statistics,
         the run's variant identity, and the instrument that actually scored it.
Dependencies: datetime, json, logging, pathlib; calibration (run_calibration),
         calibration_records (LABELS_FILE, CalibrationLabel, read_calibration_labels),
         eval_records (read_transcript), judge_identity (resolve_judge_identity),
         latency_stats (latency_summary), retrieval_summary (RETRIEVAL_METRICS_FILE),
         run_status (read_run_status),
         summary (summarize_from_dir), trend_store (LabelsGenerationMismatchError,
         RateWithCI, ScorerKappa, TrendRow), comparability (ComparabilityKey —
         imported inside comparability_key, since comparability imports trend_store
         and a module-level import would read as a cycle to a future reader even
         though it is not one)
Used by: scripts/record_trend_and_gate.py (which re-exports build_trend_row and owns
         the CLI, the baseline resolution and the gate flow)
Does NOT: choose a baseline, decide whether anything regressed, or write anything.

WHY THIS IS A SEPARATE MODULE
It was inline in scripts/record_trend_and_gate.py until the judge-identity work
(DEC-197) pushed that file to 319 lines, past the 300-line cap. Assembling a row from
artifacts and orchestrating record-then-gate are different jobs, and only the first
one is worth importing from anywhere else.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from calibration import run_calibration
from calibration_records import LABELS_FILE, CalibrationLabel, read_calibration_labels
from eval_records import read_transcript
from judge_identity import resolve_judge_identity
from latency_stats import latency_summary
from retrieval_summary import RETRIEVAL_METRICS_FILE
from run_status import RunStatus, read_run_status
from summary import EvalSummary, summarize_from_dir
from trend_store import LabelsGenerationMismatchError, RateWithCI, ScorerKappa, TrendRow

if TYPE_CHECKING:
    from comparability import ComparabilityKey

_UNKNOWN_HARNESS_VERSION: str = "unknown"
_RUN_STATUS_FILENAME: str = "run_status.json"
TRANSCRIPT_FILENAME: str = "outputs.jsonl"
"""The generation pass's transcript; also the file --print-baseline probes for."""

_logger = logging.getLogger(__name__)

def _rate_with_ci(rate: float | None, ci_low: float | None, ci_high: float | None, n: int) -> RateWithCI:
    """Build a RateWithCI, tolerating an unmeasured (all-None) rate."""
    return RateWithCI(rate=rate, ci_low=ci_low, ci_high=ci_high, n=n)


def _harness_version(gen_dir: Path) -> str:
    """Read harness_version from a gen_dir's meta.json, or a sentinel if absent."""
    transcript = read_transcript(gen_dir / TRANSCRIPT_FILENAME)
    if transcript.config is None:
        return _UNKNOWN_HARNESS_VERSION
    # str(...): pydantic field access resolves as Any to mypy here (no-any-return
    # otherwise) — the same type-checker gap regression_gate._rate_regressed
    # documents, not a real runtime ambiguity.
    return str(transcript.config.harness_version)


def _receipt_token_budget(gen_dir: Path) -> int | None:
    """Return the prompt token budget the ENGINE reported holding this run's turns to.

    Read off the transcript's context receipts, never off meta.json: meta.json is written by
    the CLIENT (run_config), and the budget belongs to the engine. A client-side stamp would
    publish a number nothing verified — the same class of defect that let the 2026-08-25 arm
    claim a SHA it never ran.

    Args:
        gen_dir: The completed run's generation directory.
    Returns:
        The single budget every receipt agrees on. None when no turn reported a receipt,
        which is every arm generated before the field existed. None plus a warning when
        turns disagree: that is a finding about the run, not a number to average away.
    """
    budgets = {
        record.context_receipt.prompt_token_budget
        for record in read_transcript(gen_dir / TRANSCRIPT_FILENAME).records
        if record.context_receipt is not None
    }
    if not budgets:
        return None
    if len(budgets) > 1:
        _logger.warning(
            "context receipts disagree on prompt_token_budget in %s: %s — recording None",
            gen_dir,
            sorted(budgets),
        )
        return None
    # int(...): pydantic field access resolves as Any to mypy here, the same type-checker
    # gap _harness_version documents with str(...) — not a real runtime ambiguity.
    return int(budgets.pop())


def _panel_status(gen_dir: Path, status_path: Path | None) -> RunStatus | None:
    """Load the judge pass's run_status.json, or None when it isn't there.

    The panel's agreement statistics are read off this file rather than
    recomputed by re-joining outputs.jsonl with judged_panel_votes.jsonl: the
    judge pass already did that join and wrote the result (DEC-189), and
    duplicating it would let the two drift apart the way judged.jsonl's two
    writers did (DEC-187).
    """
    return read_run_status(status_path or gen_dir / _RUN_STATUS_FILENAME)


def _read_labels(labels_path: Path) -> list[CalibrationLabel]:
    """Read calibration labels, tolerating a missing file.

    Args:
        labels_path: Calibration labels file; a missing file yields an empty list
            rather than raising — the rate axis is independent of calibration, and
            an uncalibrated run is a valid (if less informative) trend row.
    Returns:
        The file's rows in order, or [] when the file does not exist.
    """
    return read_calibration_labels(labels_path) if labels_path.exists() else []


def _scorer_kappas(labels: list[CalibrationLabel]) -> tuple[ScorerKappa, ...]:
    """Compute every calibrated scorer's kappa from already-read human labels.

    Args:
        labels: Calibration labels already read from disk (see _read_labels).
    Returns:
        One ScorerKappa per scorer whose labels clear label_adequacy.check_label_adequacy.
    """
    reports = run_calibration(labels, print_fn=lambda *_a, **_k: None) if labels else []
    return tuple(
        ScorerKappa(scorer=r.scorer, kappa=r.kappa, ci_low=r.kappa_lo, ci_high=r.kappa_hi, n=r.counts.n)
        for r in reports
    )


def _labels_provenance(labels: list[CalibrationLabel]) -> tuple[str | None, int | None]:
    """Return (labels_gen_id, labels_n) — which generation the labels name, and how many.

    Args:
        labels: Calibration labels already read from disk (see _read_labels).
    Returns:
        (None, None) when there are no labels. (None, n) when the labels carry no gen_id
        (legacy rows, CalibrationLabel.gen_id defaults to "") or name more than one —
        either way the generation is not attributable, which is a fact worth keeping
        distinct from "there are no labels at all". Otherwise the single gen_id every
        row names, and the row count.
    """
    if not labels:
        return None, None
    gen_ids = {label.gen_id for label in labels if label.gen_id}
    return (gen_ids.pop() if len(gen_ids) == 1 else None), len(labels)


def _battery_rates(eval_summary: EvalSummary) -> tuple[RateWithCI, RateWithCI, RateWithCI]:
    """Extract the three published battery rates, each with its Wilson CI and n.

    The guard side is two rates, never one (DEC-243): `case_adv_`/`case_neg_` are scored
    on the YAML battery's expectations and `ah_demo_` on refusal_judge /
    anti_hallucination_grounded, so a row carrying their union would trend a number that
    means two things. `TrendRow.guard` is left unset for that reason.

    Args:
        eval_summary: The RunSummary from summary.summarize_from_dir.
    Returns:
        (adversarial, anti_hallucination, capability). Any may carry rate=None when no
        turns of that battery ran; an unmeasured rate is recorded, never skipped.
    """
    return (
        _rate_with_ci(
            eval_summary.adversarial_rate, eval_summary.adversarial_ci_low,
            eval_summary.adversarial_ci_high, eval_summary.adversarial_turns,
        ),
        _rate_with_ci(
            eval_summary.anti_hallucination_rate, eval_summary.anti_hallucination_ci_low,
            eval_summary.anti_hallucination_ci_high, eval_summary.anti_hallucination_turns,
        ),
        _rate_with_ci(
            eval_summary.capability_rate, eval_summary.capability_ci_low,
            eval_summary.capability_ci_high, eval_summary.capability_turns,
        ),
    )


def _inconclusive_rate(eval_summary: EvalSummary) -> float | None:
    """Fraction of judged expectations that returned no verdict; None when nothing ran."""
    evaluated: int = eval_summary.evaluated_cases
    if evaluated <= 0:
        return None
    return float(eval_summary.inconclusive_failures) / float(evaluated)


def build_trend_row(
    gen_id: str,
    gen_dir: Path,
    *,
    labels_path: Path = LABELS_FILE,
    recorded_at: str | None = None,
    status_path: Path | None = None,
    allow_foreign_labels: bool = False,
) -> TrendRow:
    """Assemble a TrendRow from a completed run's on-disk artifacts.

    Args:
        gen_id: The generation id this row records.
        gen_dir: Directory holding outputs.jsonl / judged.jsonl / deterministic_judged.jsonl.
        labels_path: Calibration labels file to compute per-scorer kappa from.
        recorded_at: ISO-8601 override (tests only); real callers omit it.
        status_path: run_status.json override; defaults to gen_dir's own.
        allow_foreign_labels: See _check_labels_attribution.
    Returns:
        A TrendRow ready for trend_store.append_trend_row. Panel agreement is
        recorded chance-corrected (kappa with its interval, per criterion, plus
        the repeat-flip split) as well as raw — raw pairwise agreement alone is
        inflated by the pass base rate (DEC-188).
    Raises:
        LabelsGenerationMismatchError: See _check_labels_attribution.
    """
    eval_summary = summarize_from_dir(gen_dir)
    status = _panel_status(gen_dir, status_path)
    return TrendRow(
        gen_id=gen_id,
        harness_version=_harness_version(gen_dir),
        recorded_at=recorded_at or datetime.now(timezone.utc).isoformat(),
        inconclusive_rate=_inconclusive_rate(eval_summary),
        prompt_token_budget=_receipt_token_budget(gen_dir),  # the engine's, not meta.json's
        **_labels_fields(gen_id, labels_path, allow_foreign_labels),
        **_rate_fields(eval_summary),
        **_panel_fields(status),
        **_variant_fields(gen_dir),
        **_latency_fields(gen_dir),
    )


def _latency_fields(gen_dir: Path) -> dict[str, float | None]:
    """Compute per-turn p50/p95 latency from the transcript's duration_ms values.

    Args:
        gen_dir: The completed run's generation directory.
    Returns:
        latency_p50_ms and latency_p95_ms as TrendRow kwargs; both None when the
        transcript has no records (see latency_stats.latency_summary).
    """
    records = read_transcript(gen_dir / TRANSCRIPT_FILENAME).records
    p50, p95 = latency_summary(records)
    return {"latency_p50_ms": p50, "latency_p95_ms": p95}


def _labels_fields(
    gen_id: str, labels_path: Path, allow_foreign_labels: bool
) -> dict[str, object]:
    """Read labels, verify attribution, and return the kappa/provenance TrendRow kwargs.

    Split out of build_trend_row purely to keep that function under the 40-line cap —
    this is glue, not new computation.

    Args:
        gen_id: The generation this row is being recorded for.
        labels_path: Calibration labels file to compute per-scorer kappa from.
        allow_foreign_labels: See _check_labels_attribution.
    Returns:
        scorer_kappas, labels_gen_id and labels_n as TrendRow kwargs.
    Raises:
        LabelsGenerationMismatchError: See _check_labels_attribution.
    """
    labels = _read_labels(labels_path)
    labels_gen_id, labels_n = _labels_provenance(labels)
    _check_labels_attribution(gen_id, labels_gen_id, allow_foreign_labels)
    return {
        "scorer_kappas": _scorer_kappas(labels),
        "labels_gen_id": labels_gen_id,
        "labels_n": labels_n,
    }


def _check_labels_attribution(
    gen_id: str, labels_gen_id: str | None, allow_foreign_labels: bool
) -> None:
    """Refuse to build a row whose labels name a different generation.

    Args:
        gen_id: The generation this row is being recorded for.
        labels_gen_id: The generation the calibration labels actually name; None when
            unattributable (no labels, or labels naming zero or more than one gen_id) —
            unattributable labels never refuse, since there is no claim to contradict.
        allow_foreign_labels: Set True to record the row anyway.
    Raises:
        LabelsGenerationMismatchError: labels_gen_id names another generation and the
            override was not passed.
    """
    if labels_gen_id is not None and labels_gen_id != gen_id and not allow_foreign_labels:
        raise LabelsGenerationMismatchError(gen_id, labels_gen_id)



def _rate_fields(eval_summary: EvalSummary) -> dict[str, RateWithCI]:
    """The three published battery rates as TrendRow kwargs.

    `guard` is deliberately absent: DEC-243 retired the combined rate, and omitting the
    key is what stops a new row from carrying one.
    """
    adversarial, anti_hallucination, capability = _battery_rates(eval_summary)
    return {
        "guard_adversarial": adversarial,
        "guard_anti_hallucination": anti_hallucination,
        "capability": capability,
    }


def _panel_fields(status: RunStatus | None) -> dict:
    """Panel agreement fields as TrendRow kwargs; all None when no panel ran."""
    return {
        "panel_agreement_rate": status.raw_agreement if status else None,
        "panel_kappa": status.panel_kappa if status else None,
        "kappa_by_criterion": status.kappa_by_criterion if status else (),
        "repeat_flips": status.repeat_flips if status else None,
    }


def comparability_key(gen_dir: Path) -> "ComparabilityKey":
    """Build a run's comparability key without assembling its whole trend row.

    Used by --print-baseline, which must answer "which row would this be gated
    against" cheaply, before the summarise-and-calibrate work build_trend_row does.

    Args:
        gen_dir: The completed run's generation directory.
    Returns:
        The ComparabilityKey carrying this run's harness_version and the judge
        identity that actually scored it.
    """
    from comparability import ComparabilityKey

    return ComparabilityKey(
        harness_version=_harness_version(gen_dir),
        judge_identity=str(_variant_fields(gen_dir)["judge_identity"]),
    )


def _variant_fields(gen_dir: Path) -> dict[str, object]:
    """Read the run's variant identity from meta.json, plus retrieval precision if measured.

    Every value is optional: the store is append-only and holds rows written before these
    fields existed, and a run generated without a retrieval pass simply has no precision.
    Missing is recorded as None rather than skipped, so a gap is visible in the trend
    rather than looking like continuity.
    """
    config: dict[str, object] = {}
    meta_path = gen_dir / "meta.json"
    if meta_path.exists():
        try:
            config = json.loads(meta_path.read_text(encoding="utf-8")).get("config", {})
        except (json.JSONDecodeError, OSError):
            config = {}

    precision: float | None = None
    metrics_path = gen_dir / RETRIEVAL_METRICS_FILE
    if metrics_path.exists():
        try:
            precision = json.loads(metrics_path.read_text(encoding="utf-8")).get("mean_precision_at_k")
        except (json.JSONDecodeError, OSError):
            precision = None

    return {
        # The instrument that actually scored the run, not the one meta.json was
        # configured with: since --panel landed, one generation config can be scored
        # either way under a byte-identical meta.json (DEC-190). This is a
        # comparability condition in the trend gate, unlike the variant fields below,
        # which are the independent variable (DEC-194 decision 5, DEC-197).
        "judge_identity": resolve_judge_identity(gen_dir, config.get("judge_model")) or "",
        "retrieval_profile": config.get("retrieval_profile"),
        "dialogue_prompt_hash": config.get("dialogue_prompt_hash"),
        "git_sha": config.get("git_sha"),
        # prompt_token_budget is deliberately absent: it comes from the engine's context
        # receipts (_receipt_token_budget), not from this client-written config block, where
        # nothing ever wrote it and it read null on every row.
        "mean_precision_at_k": precision,
    }
