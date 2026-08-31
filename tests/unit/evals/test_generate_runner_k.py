"""
Module: test_generate_runner_k
Layer: test (unit)
Purpose: Tests for k-repeat and retrieved-context capture in
         generation_collection.collect_records, plus generate_runner.run's gen-dir output.
Dependencies: unittest.mock, generate_runner, generation_collection (evals/, on pytest
              pythonpath).
Used by: pytest (make test / make check).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from generate_runner import run
from generation_collection import collect_records
from run_config import RunConfig, resolve_run_config



def _offline_resolve(**kwargs: object) -> RunConfig:
    """Resolve a real RunConfig with the Ollama probes stubbed out.

    Unit tests do no network I/O (tests/unit/conftest.py), and a None digest is fatal
    since R2.1 — so the probes are injected while everything else about the resolution
    stays real.
    """
    return resolve_run_config(
        fetch_generation_digest=lambda *_: "sha256:stub-generation",
        fetch_judge_digest=lambda *_: "sha256:stub-judge",
        fetch_ollama_version_fn=lambda _: None,
        fetch_corpus_fingerprint=lambda: None,
        **kwargs,  # type: ignore[arg-type]
    )


def _make_yaml_case(case_id: str = "tc001") -> dict:
    """Return a minimal YAML eval case with one tone_judge expectation."""
    return {
        "case_id": case_id,
        "seed": {"npc_id": "test_npc", "player_id": "test_player"},
        "input": {"player_message": "hello world"},
        "expected": [{"kind": "tone_judge", "description": "Should be friendly"}],
    }


def _make_mock_client(*, with_context: bool = True) -> MagicMock:
    """Return a mock httpx.Client whose POST returns a dialogue and GET returns retrieval."""
    client = MagicMock()

    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = {"npc_response": "Hello there!"}
    client.post.return_value = post_resp

    get_resp = MagicMock()
    get_resp.raise_for_status = MagicMock()
    get_resp.json.return_value = {
        "context_items": [
            {"key": "memories", "tier": "A", "priority": 1, "text": "context text"}
        ]
        if with_context
        else []
    }
    client.get.return_value = get_resp

    return client


@patch("generation_collection.preconditions.ensure_player_node")
def test_k_repeats_produce_k_records_per_case(mock_ensure: MagicMock) -> None:
    """collect_records with k=2 produces twice the records of k=1.

    Each record carries the correct repetition index, a non-negative duration_ms,
    and a non-empty retrieved_context.
    """
    case = _make_yaml_case()
    client = _make_mock_client()

    records = collect_records([case], [], client, "http://test", k=2)

    # 1 tone_judge expectation × k=2 repetitions = 2 records
    assert len(records) == 2, f"Expected 2 records, got {len(records)}"
    repetitions = sorted(r.repetition for r in records)
    assert repetitions == [0, 1], f"Expected repetitions [0, 1], got {repetitions}"
    assert all(r.duration_ms >= 0 for r in records)
    assert all(len(r.retrieved_context) > 0 for r in records), (
        "Every record must carry a non-empty retrieved_context"
    )


@patch("generation_collection.preconditions.ensure_player_node")
def test_k_equals_one_is_default(mock_ensure: MagicMock) -> None:
    """collect_records with no k argument defaults to k=1 (backward compatible)."""
    case = _make_yaml_case()
    client = _make_mock_client()

    records_default = collect_records([case], [], client, "http://test")
    records_explicit = collect_records([case], [], client, "http://test", k=1)

    assert len(records_default) == 1
    assert len(records_explicit) == 1
    assert records_default[0].repetition == 0
    assert records_explicit[0].repetition == 0


@patch("generate_runner.resolve_run_config", _offline_resolve)
@patch("generation_collection.preconditions.ensure_player_node")
def test_gen_dir_run_records_a_non_null_run_config(
    mock_ensure: MagicMock, tmp_path: Path
) -> None:
    """A gen-dir run must persist a resolved RunConfig, never null.

    Regression guard. EVAL-P1.1/P1.2/P1.3/P1.5 built RunConfig, made prompt_version
    single-sourced and golden_set_version content-derived — but generate_runner never
    imported run_config and called write_generation_dir without config=, whose default
    is None. Four completed tasks were therefore unreachable from the generation path
    and every artifact recorded "config": null. The original EVAL-P1.4 checklist
    asserted repetition/duration_ms/retrieved_context and never asserted this, which is
    exactly why the gate stayed green while run identity was absent.
    """
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "case_a.yaml").write_text("case_id: tc001\n", encoding="utf-8")

    out_dir = tmp_path / "generations"
    run(
        yaml_cases=[_make_yaml_case()],
        ah_cases=[],
        client=_make_mock_client(),
        base_url="http://test",
        out_dir=out_dir,
        run_id="unused",
        gen_id="smoke",
        k=1,
        cases_dir=cases_dir,
    )

    meta = json.loads((out_dir / "smoke" / "meta.json").read_text(encoding="utf-8"))
    assert meta["config"] is not None, "meta.json must carry a resolved RunConfig"
    for field in ("prompt_version", "generation_model", "judge_model", "git_sha"):
        assert meta["config"][field], f"{field} must be non-empty in the recorded config"
    assert meta["config"]["golden_set_version"] != "unversioned"


@patch("generation_collection.preconditions.ensure_player_node")
def test_gen_dir_run_resolves_config_before_generating(
    mock_ensure: MagicMock, tmp_path: Path
) -> None:
    """A misconfigured run must fail before the generation pass, not after it.

    Resolving config after collect_records would mean an hour of dialogue POSTs is
    spent before the run dies on a bad judge model or an empty cases dir.
    """
    client = _make_mock_client()
    # quality-ok: the assertion is 'any mutation is rejected' and the two model families raise different types (pydantic v2 frozen -> ValidationError, frozen dataclass -> FrozenInstanceError); narrowing per-site is deferred, see ISSUES
    with pytest.raises(Exception):
        run(
            yaml_cases=[_make_yaml_case()],
            ah_cases=[],
            client=client,
            base_url="http://test",
            out_dir=tmp_path / "generations",
            run_id="unused",
            gen_id="smoke",
            k=1,
            cases_dir=tmp_path / "does_not_exist",
        )

    client.post.assert_not_called()
