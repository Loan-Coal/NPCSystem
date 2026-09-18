"""
Module: sentence_encoder
Layer: retrieval
Purpose: Lazy-loaded sentence-transformers encoder with GPU/CPU auto-detect.
Does NOT: persist models to disk or perform batch indexing.
Dependencies injected: None (model loaded via lru_cache on first call).
Used by: retrieval.embedding_index._embed_text
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, cast

_logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_encoder(model_name: str) -> Any:
    """Return a cached SentenceTransformer for model_name, auto-selecting device.

    First call loads the model (~80 MB for all-MiniLM-L6-v2) and caches it.
    Subsequent calls return the cached instance immediately.

    Args:
        model_name: HuggingFace model identifier (e.g. "all-MiniLM-L6-v2").

    Returns:
        SentenceTransformer instance on the best available device.
    """

    from sentence_transformers import SentenceTransformer  # lazy: keeps module importable without the package

    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    except ImportError:
        device = "cpu"

    _logger.info("Loading embedding model %s on %s", model_name, device)
    return SentenceTransformer(model_name, device=device)


def warm_up_encoder(model_name: str, *, enabled: bool) -> None:
    """Force the lru_cache for get_encoder to populate at boot.

    Intended for call via asyncio.to_thread from the application lifespan so the
    ~21 s cold load (torch import + model init) happens before the first request
    that needs an embedding (ISSUE-356, SEV-07).

    Fails soft — any exception is logged as a warning and swallowed so a failed
    warm-up never prevents boot; the lazy path in get_encoder still works.

    Args:
        model_name: HuggingFace model identifier (e.g. "all-MiniLM-L6-v2").
        enabled: When False, returns immediately without loading anything.
    """
    if not enabled:
        return
    try:
        get_encoder(model_name)
        _logger.info("embedding.warmup_complete model=%s", model_name)
    except Exception:
        _logger.warning(
            "embedding.warmup_failed model=%s — boot continues with lazy encoder load",
            model_name,
        )


def embed(text: str, model_name: str) -> list[float]:
    """Return a normalized float vector for text using model_name.

    Args:
        text: Input text to encode.
        model_name: HuggingFace model identifier.

    Returns:
        Normalized list of floats with length equal to the model's output dimension.
    """

    encoder = get_encoder(model_name)
    vector = encoder.encode(text, normalize_embeddings=True)
    return cast(list[float], vector.tolist())
