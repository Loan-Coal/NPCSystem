"""
Module: test_prelabel_runner
Layer: test (unit)
Purpose: Unit tests for prelabel_runner.py — the committed replacement for the ad-hoc
         PowerShell pre-labelling loop (DEC-272). The behaviours that matter most and
         are pinned hardest here: the prompt goes on stdin (never argv, which the
         largest batch overflows), a resumed run relabels nothing, and a contaminated
         or unparseable response line is dropped with a reason instead of being written.
Dependencies: pytest, unittest.mock, prelabel_runner (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import prelabel_runner
from prelabel_runner import (
    PrelabelInvocationError,
    append_rows,
    batch_keys,
    build_batch_prompt,
    existing_keys,
    invoke_labeller,
    load_prompt,
    main,
    parse_response_rows,
    run_prelabelling,
)


def _batch_file(tmp_path: Path, name: str = "batch_001.json", n: int = 2) -> Path:
    """Write a minimal exported batch file and return its path."""
    items = [
        {"record_id": f"case_{i:03d}:tone_judge:0#r0", "scorer": "tone_judge", "output_text": f"text {i}"}
        for i in range(n)
    ]
    path = tmp_path / name
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def _response_for(n: int = 2) -> str:
    """A well-formed labeller response covering n items."""
    return "\n".join(
        json.dumps({
            "record_id": f"case_{i:03d}:tone_judge:0#r0",
            "scorer": "tone_judge",
            "pre_label": True,
            "notes": "fine",
        })
        for i in range(n)
    )


# ---------------------------------------------------------------------------
# Prompt handling
# ---------------------------------------------------------------------------


def test_load_prompt_strips_a_leading_html_comment(tmp_path: Path) -> None:
    """The comment holds run instructions the prompt files warn must not reach the model."""
    path = tmp_path / "p.md"
    path.write_text("<!--\n  run instructions\n-->\n\nYou are labelling.\n", encoding="utf-8")

    assert load_prompt(path) == "You are labelling."


def test_load_prompt_leaves_a_prompt_without_a_comment_alone(tmp_path: Path) -> None:
    path = tmp_path / "p.md"
    path.write_text("You are labelling.\n", encoding="utf-8")

    assert load_prompt(path) == "You are labelling."


def test_build_batch_prompt_uses_the_declared_delimiters() -> None:
    prompt = build_batch_prompt("PROMPT", '[{"a": 1}]')

    assert prompt.startswith("PROMPT")
    assert "<BATCH>\n[{\"a\": 1}]\n</BATCH>" in prompt


def test_the_real_opus_prompt_loads_and_loses_its_provenance_block() -> None:
    """Guards the default: OPUS_LABEL_PROMPT.md's comment must not reach the model."""
    text = load_prompt(prelabel_runner.DEFAULT_PROMPT_PATH)

    assert text
    assert not text.lstrip().startswith("<!--")
    assert "criteria_manifest_sha256" not in text


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def test_parse_keeps_valid_rows_and_ignores_surrounding_prose() -> None:
    stdout = "Here are the labels:\n" + _response_for(2) + "\nDone.\n"

    rows, rejected = parse_response_rows(stdout)

    assert [r.record_id for r in rows] == ["case_000:tone_judge:0#r0", "case_001:tone_judge:0#r0"]
    assert rejected == []


def test_parse_rejects_a_contaminated_row() -> None:
    """A row carrying output_text or scorer_verdict has seen the answer — importer's rule."""
    stdout = json.dumps({
        "record_id": "case_000:tone_judge:0#r0", "scorer": "tone_judge",
        "pre_label": True, "notes": "n", "scorer_verdict": True,
    })

    rows, rejected = parse_response_rows(stdout)

    assert rows == []
    assert len(rejected) == 1
    assert "case_000" in rejected[0]


def test_parse_rejects_unparseable_and_schema_invalid_lines() -> None:
    stdout = '{"record_id": "x", "scorer"\n{"record_id": "y", "scorer": "s"}\n'

    rows, rejected = parse_response_rows(stdout)

    assert rows == []
    assert len(rejected) == 2  # one unparseable, one missing pre_label


def test_parse_of_an_empty_response_yields_nothing() -> None:
    assert parse_response_rows("") == ([], [])


# ---------------------------------------------------------------------------
# Resume bookkeeping
# ---------------------------------------------------------------------------


def test_existing_keys_of_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert existing_keys(tmp_path / "absent.jsonl") == set()


def test_existing_keys_tolerates_a_truncated_trailing_line(tmp_path: Path) -> None:
    """An interrupted run can leave a half-written line; it must not blind the resume."""
    path = tmp_path / "raw.jsonl"
    path.write_text(_response_for(2) + '\n{"record_id": "case_002", "sco', encoding="utf-8")

    assert existing_keys(path) == {
        ("case_000:tone_judge:0#r0", "tone_judge"),
        ("case_001:tone_judge:0#r0", "tone_judge"),
    }


def test_batch_keys_reads_record_id_and_scorer_in_file_order(tmp_path: Path) -> None:
    assert batch_keys(_batch_file(tmp_path)) == [
        ("case_000:tone_judge:0#r0", "tone_judge"),
        ("case_001:tone_judge:0#r0", "tone_judge"),
    ]


def test_append_rows_round_trips_through_existing_keys(tmp_path: Path) -> None:
    rows, _ = parse_response_rows(_response_for(2))
    path = tmp_path / "raw.jsonl"

    append_rows(path, rows)

    assert len(existing_keys(path)) == 2


# ---------------------------------------------------------------------------
# invoke_labeller — transport
# ---------------------------------------------------------------------------


def test_invoke_passes_the_prompt_on_stdin_not_argv() -> None:
    """argv cannot carry it: the largest batch plus prompt is ~53k chars vs a 32,767 limit."""
    with patch("prelabel_runner.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        invoke_labeller("PROMPT BODY", cli="claude", model="opus", timeout=1.0)

    args, kwargs = run.call_args
    assert args[0] == ["claude", "-p", "--model", "opus"]
    assert kwargs["input"] == "PROMPT BODY"
    assert not any("PROMPT BODY" in part for part in args[0])


def test_invoke_raises_on_a_non_zero_exit() -> None:
    with patch("prelabel_runner.subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
        with pytest.raises(PrelabelInvocationError, match="exited 1"):
            invoke_labeller("p", cli="claude", model="opus", timeout=1.0)


def test_invoke_raises_a_clear_error_when_the_cli_is_missing() -> None:
    with patch("prelabel_runner.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(PrelabelInvocationError, match="not found on PATH"):
            invoke_labeller("p", cli="nope", model="opus", timeout=1.0)


def test_invoke_raises_on_timeout() -> None:
    with patch("prelabel_runner.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 1.0)):
        with pytest.raises(PrelabelInvocationError, match="timed out"):
            invoke_labeller("p", cli="claude", model="opus", timeout=1.0)


# ---------------------------------------------------------------------------
# run_prelabelling
# ---------------------------------------------------------------------------


def test_a_run_writes_validated_rows_and_reports_totals(tmp_path: Path) -> None:
    batch = _batch_file(tmp_path)
    out = tmp_path / "raw.jsonl"

    with patch("prelabel_runner.invoke_labeller", return_value=_response_for(2)):
        summary = run_prelabelling([batch], out, prompt_text="P", log_fn=lambda _: None)

    assert summary.rows_written == 2
    assert summary.batches_run == 1
    assert summary.batches_skipped == 0
    assert len(existing_keys(out)) == 2


def test_a_second_run_over_the_same_batch_relabels_nothing(tmp_path: Path) -> None:
    batch = _batch_file(tmp_path)
    out = tmp_path / "raw.jsonl"

    with patch("prelabel_runner.invoke_labeller", return_value=_response_for(2)) as invoke:
        run_prelabelling([batch], out, prompt_text="P", log_fn=lambda _: None)
        summary = run_prelabelling([batch], out, prompt_text="P", log_fn=lambda _: None)

    assert invoke.call_count == 1
    assert summary.batches_skipped == 1
    assert summary.rows_written == 0


def test_a_dry_run_invokes_nothing_but_a_real_run_does(tmp_path: Path) -> None:
    """Differential on purpose: the wet half proves the patched symbol is actually live,
    so the dry half's zero cannot pass vacuously against a mis-targeted patch."""
    batch = _batch_file(tmp_path)
    out = tmp_path / "raw.jsonl"

    with patch("prelabel_runner.invoke_labeller", return_value=_response_for(2)) as invoke:
        dry_summary = run_prelabelling([batch], out, prompt_text="P", dry_run=True, log_fn=lambda _: None)
        dry_calls, wrote_on_dry = invoke.call_count, out.exists()
        run_prelabelling([batch], out, prompt_text="P", dry_run=False, log_fn=lambda _: None)
        wet_calls = invoke.call_count

    assert (dry_calls, wet_calls) == (0, 1)
    assert wrote_on_dry is False
    assert dry_summary.rows_written == 0
    assert out.exists()


def test_rows_outside_the_requested_batch_are_still_deduped(tmp_path: Path) -> None:
    """A labeller that repeats a row across batches must not double-write it."""
    first, second = _batch_file(tmp_path, "batch_001.json"), _batch_file(tmp_path, "batch_002.json", n=3)
    out = tmp_path / "raw.jsonl"

    with patch("prelabel_runner.invoke_labeller", side_effect=[_response_for(2), _response_for(3)]):
        summary = run_prelabelling([first, second], out, prompt_text="P", log_fn=lambda _: None)

    assert summary.rows_written == 3  # 2 then only the 1 genuinely new row
    assert len(existing_keys(out)) == 3


def test_a_row_the_labeller_invented_is_rejected_not_written(tmp_path: Path) -> None:
    """A dropped '#r<n>' suffix would be normalised to r0 at import and mis-attached."""
    batch = _batch_file(tmp_path, n=1)
    out = tmp_path / "raw.jsonl"
    stray = json.dumps({
        "record_id": "case_000:tone_judge:0",  # same case, suffix dropped
        "scorer": "tone_judge", "pre_label": True, "notes": "n",
    })

    with patch("prelabel_runner.invoke_labeller", return_value=_response_for(1) + "\n" + stray):
        summary = run_prelabelling([batch], out, prompt_text="P", log_fn=lambda _: None)

    assert summary.rows_written == 1
    assert summary.rows_rejected == 1
    assert existing_keys(out) == {("case_000:tone_judge:0#r0", "tone_judge")}


def test_rejections_are_counted_and_surface_in_the_summary(tmp_path: Path) -> None:
    batch = _batch_file(tmp_path)
    out = tmp_path / "raw.jsonl"

    with patch("prelabel_runner.invoke_labeller", return_value='{"record_id": "x", "scorer": "s"}'):
        summary = run_prelabelling([batch], out, prompt_text="P", log_fn=lambda _: None)

    assert summary.rows_written == 0
    assert summary.rows_rejected == 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_main_refuses_to_write_over_the_labels_artifact(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    exit_code = main([
        "--batch-dir", str(tmp_path),
        "--out", str(prelabel_runner.LABELS_FILE),
        "--dry-run",
    ])

    assert exit_code == 2
    assert "refusing to write" in capsys.readouterr().err


def test_main_reports_an_empty_batch_directory(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    exit_code = main(["--batch-dir", str(tmp_path), "--out", str(tmp_path / "raw.jsonl"), "--dry-run"])

    assert exit_code == 2
    assert "no batch_*.json" in capsys.readouterr().err


def test_main_dry_run_plans_batches_without_invoking_but_a_real_run_invokes(
    tmp_path: Path, capsys  # noqa: ANN001
) -> None:
    """Same differential shape as the run_prelabelling test, at the CLI boundary."""
    _batch_file(tmp_path)
    out = tmp_path / "raw.jsonl"

    with patch("prelabel_runner.invoke_labeller", return_value=_response_for(2)) as invoke:
        dry_exit = main(["--batch-dir", str(tmp_path), "--out", str(out), "--dry-run"])
        dry_calls = invoke.call_count
        wet_exit = main(["--batch-dir", str(tmp_path), "--out", str(out)])
        wet_calls = invoke.call_count

    assert (dry_calls, wet_calls) == (0, 1)
    assert (dry_exit, wet_exit) == (0, 0)
    assert "DRY RUN" in capsys.readouterr().out


def test_main_limit_caps_the_batches_considered(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    _batch_file(tmp_path, "batch_001.json")
    _batch_file(tmp_path, "batch_002.json")

    main(["--batch-dir", str(tmp_path), "--out", str(tmp_path / "raw.jsonl"), "--dry-run", "--limit", "1"])

    assert "1 batch(es)" in capsys.readouterr().out


def test_main_writes_a_provenance_log_on_a_real_run(tmp_path: Path) -> None:
    _batch_file(tmp_path)
    out = tmp_path / "raw.jsonl"

    with patch("prelabel_runner.invoke_labeller", return_value=_response_for(2)):
        main(["--batch-dir", str(tmp_path), "--out", str(out), "--gen-id", "k3_test"])

    log_text = out.with_suffix(".log").read_text(encoding="utf-8")
    assert "gen_id=k3_test" in log_text
    assert "model=opus" in log_text
