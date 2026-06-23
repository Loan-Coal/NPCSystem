"""
test_sentence_encoder.py - Unit tests for sentence encoder and embedding_index._embed_text.

Does NOT: load a real SentenceTransformer model.

Dependencies injected: sentence_encoder.embed is mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import ensures the module is in sys.modules before patch() accesses it.
import npc_engine.retrieval.embedding.sentence_encoder as _sentence_encoder_module

from npc_engine.retrieval.embedding import EMBED_DIMENSION, _embed_text


_MODEL_NAME = "all-MiniLM-L6-v2"
_FAKE_VECTOR = [1.0 / (EMBED_DIMENSION ** 0.5)] * EMBED_DIMENSION


def test_embed_text_returns_zero_vector_for_empty_string() -> None:
    result = _embed_text("", _MODEL_NAME)
    assert result == [0.0] * EMBED_DIMENSION
    assert len(result) == EMBED_DIMENSION


def test_embed_text_delegates_to_sentence_encoder() -> None:
    with patch.object(_sentence_encoder_module, "embed", return_value=_FAKE_VECTOR) as mock_embed:
        result = _embed_text("hello world", _MODEL_NAME)
        mock_embed.assert_called_once_with("hello world", model_name=_MODEL_NAME)
        assert result == _FAKE_VECTOR


def test_embed_text_returns_correct_dimension() -> None:
    with patch.object(_sentence_encoder_module, "embed", return_value=_FAKE_VECTOR):
        result = _embed_text("test sentence", _MODEL_NAME)
        assert len(result) == EMBED_DIMENSION


def test_embed_dimension_constant_is_384() -> None:
    assert EMBED_DIMENSION == 384


def test_sentence_encoder_module_get_encoder_uses_lru_cache() -> None:
    assert hasattr(_sentence_encoder_module.get_encoder, "cache_info"), (
        "get_encoder must be decorated with @lru_cache"
    )


def test_sentence_encoder_embed_calls_get_encoder() -> None:
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: _FAKE_VECTOR)

    with patch.object(_sentence_encoder_module, "get_encoder", return_value=mock_encoder):
        result = _sentence_encoder_module.embed("hello", _MODEL_NAME)
        mock_encoder.encode.assert_called_once_with("hello", normalize_embeddings=True)
        assert result == _FAKE_VECTOR
