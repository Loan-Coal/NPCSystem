"""
Module: _run_config_corpus
Layer: evals
Purpose: Resolve the vector store's identity into RunConfig fields — DEC-210 Decision 2.
Does NOT: populate the corpus, decide comparability, or read case files.
Dependencies injected: a fetcher callable; the live probe is the default.
Used by: evals.run_config.resolve_run_config

Split out of run_config.py because that file is at its 300-line cap. It is a coherent
unit on its own: everything here answers one question — what was the retrieval substrate
when this run started?
"""

from __future__ import annotations

import os
from typing import Any, Callable

__all__ = ["corpus_fields", "default_corpus_fetcher"]

ENGINE_BASE_URL_ENV = "EVAL_BASE_URL"
DEFAULT_ENGINE_BASE_URL = "http://localhost:8000"
API_KEY_ENV = "API_KEY_SECRET"


def default_corpus_fetcher(adapter: Any) -> Callable[[], dict[str, Any] | None]:
    """Bind the live engine probe to the environment's base URL and API key.

    Args:
        adapter: The engine_adapter module (injected to keep this import-light).
    Returns:
        A zero-argument callable returning the fingerprint dict, or None.
    """
    base_url = os.environ.get(ENGINE_BASE_URL_ENV, DEFAULT_ENGINE_BASE_URL)
    api_key = os.environ.get(API_KEY_ENV, "")
    return lambda: adapter.fetch_corpus_fingerprint(base_url, api_key)


def corpus_fields(fetch: Callable[[], dict[str, Any] | None] | None) -> dict[str, Any]:
    """Resolve the corpus fingerprint into RunConfig kwargs.

    Args:
        fetch: Fingerprint fetcher; None uses the live engine probe.
    Returns:
        Kwargs for RunConfig. EMPTY when the engine could not be asked, so the fields
        keep their None/"" defaults — a run that could not ask must not be recorded as a
        run that asked and found nothing.
    """
    import engine_adapter as _engine_adapter

    resolved = fetch if fetch is not None else default_corpus_fetcher(_engine_adapter)
    fingerprint = resolved()
    if not fingerprint:
        return {}
    return {
        "corpus_item_count": int(fingerprint["item_count"]),
        "corpus_embedding_model": str(fingerprint["embedding_model"]),
        "corpus_embedding_dim": int(fingerprint["embedding_dim"]),
        "corpus_sha": str(fingerprint.get("corpus_sha", "")),
    }
