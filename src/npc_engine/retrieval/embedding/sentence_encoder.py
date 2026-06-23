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
