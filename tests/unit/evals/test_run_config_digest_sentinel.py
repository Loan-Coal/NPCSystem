"""
Module: test_run_config_digest_sentinel
Layer: test (unit)
Purpose: T16.6 — verify that resolve_run_config with no digest injectors does not
         attempt a network call and records an explicit sentinel, not None.
         Closing CR-L15-01 from the 2026-08 review.
Dependencies: run_config (evals/, on pytest pythonpath).
Used by: pytest (make test / make check).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from run_config import UNKNOWN_DIGEST, resolve_run_config

_MINIMAL_CONFIG: dict = {
    "engine": "dialogue",
    "llm": {
        "backend": "ollama",
        "model": "test-model:7b",
        "temperature": 0.5,
        "max_tokens": 256,
        "top_p": 0.9,
        "stop_sequences": [],
    },
    "prompt": {
        "name": "dialogue_main",
        "version": 42,
    },
}


# ---------------------------------------------------------------------------
# RED anchor: T16.6 — fails today on both halves
#
# Today: the default falls back to engine_adapter.fetch_model_digest, which
# opens a socket; conftest.py blocks it; fetch_model_digest catches the error
# and returns None; _require_digest raises ModelDigestUnavailableError — the
# RunConfig is never built and both assertions are unreachable.
#
# After the fix: the default is a sentinel function (no network call).
# resolve_run_config returns a RunConfig with UNKNOWN_DIGEST — not None, not
# a raise.
# ---------------------------------------------------------------------------


def test_no_injection_does_not_attempt_network_and_records_sentinel(
    tmp_path: Path,
) -> None:
    """resolve_run_config with no digest injectors must not attempt a network call
    and must not record None — it records UNKNOWN_DIGEST instead.

    Fails today on both halves:
    - Half 1 (no network): the default calls engine_adapter.fetch_model_digest, which
      attempts a socket connect; conftest blocks it; fetch_model_digest swallows the
      NetworkAccessInUnitTestError and returns None; _require_digest raises
      ModelDigestUnavailableError. The RunConfig is never built.
    - Half 2 (no None): unreachable today — the function raises before either assertion.
    """
    config_path = tmp_path / "llm_config.yaml"
    config_path.write_text(yaml.dump(_MINIMAL_CONFIG), encoding="utf-8")

    # No fetch_generation_digest, no fetch_judge_digest, no fetch_ollama_version_fn.
    # Only inject the two non-digest non-version parameters to avoid their side-effects.
    config = resolve_run_config(
        config_path=config_path,
        fetch_corpus_fingerprint=lambda: None,
        fetch_build_sha_fn=lambda: None,
    )

    # Half 1: reaching this line means no ModelDigestUnavailableError was raised,
    # which means no socket connect was attempted for the digest path.
    # Half 2: the digest is not None; it is an explicit sentinel.
    assert config.generation_model_digest is not None
    assert config.judge_model_digest is not None
    assert config.generation_model_digest == UNKNOWN_DIGEST
    assert config.judge_model_digest == UNKNOWN_DIGEST
