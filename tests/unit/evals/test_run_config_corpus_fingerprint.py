"""
test_run_config_corpus_fingerprint.py - DEC-210 Decision 2.

DEC-194's principle is "never record a config you did not run". It covers the profile
NAME and not the retrieval SUBSTRATE, so "was RAG live during this run?" has been an
inference from tierB.items rather than a recorded fact. These pin the fingerprint.

Does NOT: reach the network — the fetcher is injected.

Dependencies injected: a stub fingerprint fetcher.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from run_config import RunConfig, resolve_run_config

_FIXTURE = {
    "item_count": 51,
    "embedding_model": "all-MiniLM-L6-v2",
    "embedding_dim": 384,
    "corpus_sha": "a1b2c3",
}


def _resolve(tmp_path: Path, fetch) -> RunConfig:
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "case.yaml").write_text("id: c1\n", encoding="utf-8")
    return resolve_run_config(
        cases_dir=cases,
        fetch_generation_digest=lambda *_: "sha256:stub-generation",
        fetch_judge_digest=lambda *_: "sha256:stub-judge",
        fetch_ollama_version_fn=lambda _: None,
        fetch_corpus_fingerprint=fetch,
    )


def test_the_corpus_fingerprint_is_recorded_beside_the_retrieval_profile(tmp_path) -> None:
    config = _resolve(tmp_path, lambda: dict(_FIXTURE))

    assert config.corpus_item_count == 51
    assert config.corpus_embedding_model == "all-MiniLM-L6-v2"
    assert config.corpus_embedding_dim == 384
    assert config.corpus_sha == "a1b2c3"


def test_an_unreachable_engine_records_an_absent_corpus_not_a_fake_one(tmp_path) -> None:
    """A zero must not be indistinguishable from 'we could not ask'."""
    config = _resolve(tmp_path, lambda: None)

    assert config.corpus_item_count is None
    assert config.corpus_sha == ""


def test_an_artifact_written_before_p8_still_loads() -> None:
    """The committed pre-P8 generations carry none of these fields."""
    config = RunConfig(
        prompt_version="v1", generation_model="qwen2.5:7b", temperature=0.7, top_p=0.9,
        max_tokens=512, judge_model="mixtral", retrieval_profile="default",
        git_sha="abc1234", golden_set_version="0" * 12, harness_version="0" * 12,
    )

    assert config.corpus_item_count is None
    assert config.corpus_embedding_model == ""
