"""
test_context_compression.py - Unit tests for ContextCompressionCache and helpers.

Does NOT: call LLM services or external APIs.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from npc_engine.retrieval.context import (
    COMPRESSION_SUFFIX,
    MIN_COMPRESSED_CHARS,
    ContextCompressionCache,
    _compress_text,
    _extract_graph_timestamp,
    build_compression_cache_key,
)
from npc_engine.retrieval.context import ContextItem
from npc_engine.retrieval.context import CHARS_PER_TOKEN_ESTIMATE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(*, key: str = "character:npc_1", text: str = "hello") -> ContextItem:
    return ContextItem(key=key, text=text, tier="tierA", priority=50)


def _make_llm_config(*, schema_ver: str = "v1", compress_ver: str = "v1") -> MagicMock:
    cfg = MagicMock()
    cfg.prompt_schema_version = schema_ver
    cfg.compression_prompt_version = compress_ver
    return cfg


# ---------------------------------------------------------------------------
# build_compression_cache_key
# ---------------------------------------------------------------------------


def test_cache_key_is_four_tuple():
    key = build_compression_cache_key(
        node_id="npc_1",
        node_type="Character",
        prompt_schema_version="v1",
        compression_prompt_version="c1",
    )
    assert len(key) == 4


def test_cache_key_deterministic():
    kwargs = dict(node_id="npc_1", node_type="Character", prompt_schema_version="v1", compression_prompt_version="c1")
    assert build_compression_cache_key(**kwargs) == build_compression_cache_key(**kwargs)


def test_cache_key_different_versions_differ():
    k1 = build_compression_cache_key(node_id="x", node_type="T", prompt_schema_version="v1", compression_prompt_version="c1")
    k2 = build_compression_cache_key(node_id="x", node_type="T", prompt_schema_version="v2", compression_prompt_version="c1")
    assert k1 != k2


def test_cache_key_different_nodes_differ():
    k1 = build_compression_cache_key(node_id="npc_1", node_type="Character", prompt_schema_version="v1", compression_prompt_version="c1")
    k2 = build_compression_cache_key(node_id="npc_2", node_type="Character", prompt_schema_version="v1", compression_prompt_version="c1")
    assert k1 != k2


# ---------------------------------------------------------------------------
# _compress_text
# ---------------------------------------------------------------------------


def test_compress_text_short_text_unchanged():
    short = "hi"
    result = _compress_text(short, target_tokens=1000)
    assert result == short


def test_compress_text_long_text_adds_suffix():
    long_text = "x" * 10000
    result = _compress_text(long_text, target_tokens=10)
    assert COMPRESSION_SUFFIX in result


def test_compress_text_long_text_shorter_than_original():
    long_text = "a" * 10000
    result = _compress_text(long_text, target_tokens=10)
    assert len(result) < len(long_text)


def test_compress_text_very_small_target_still_produces_output():
    long_text = "b" * 10000
    result = _compress_text(long_text, target_tokens=1)
    assert len(result) > 0
    assert COMPRESSION_SUFFIX in result


def test_compress_text_deterministic():
    text = "hello world " * 100
    r1 = _compress_text(text, target_tokens=5)
    r2 = _compress_text(text, target_tokens=5)
    assert r1 == r2


# ---------------------------------------------------------------------------
# _extract_graph_timestamp
# ---------------------------------------------------------------------------


def test_extract_graph_timestamp_last_graph_updated_at():
    payload = {"last_graph_updated_at": "2024-01-01T00:00:00Z"}
    text = json.dumps(payload)
    assert _extract_graph_timestamp(text) == "2024-01-01T00:00:00Z"


def test_extract_graph_timestamp_updated_at():
    payload = {"updated_at": "2024-06-15T12:00:00Z"}
    text = json.dumps(payload)
    assert _extract_graph_timestamp(text) == "2024-06-15T12:00:00Z"


def test_extract_graph_timestamp_prefers_last_graph_updated_at_first():
    payload = {"last_graph_updated_at": "2024-01-01T00:00:00Z", "updated_at": "2023-01-01T00:00:00Z"}
    text = json.dumps(payload)
    assert _extract_graph_timestamp(text) == "2024-01-01T00:00:00Z"


def test_extract_graph_timestamp_no_timestamp_fields():
    text = json.dumps({"name": "Aria"})
    assert _extract_graph_timestamp(text) is None


def test_extract_graph_timestamp_non_json_text():
    assert _extract_graph_timestamp("plain text with no JSON") is None


def test_extract_graph_timestamp_empty_string_field_skipped():
    text = json.dumps({"last_graph_updated_at": "", "updated_at": "2024-01-01T00:00:00Z"})
    assert _extract_graph_timestamp(text) == "2024-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# ContextCompressionCache.compress_item
# ---------------------------------------------------------------------------


def test_compress_item_returns_string():
    cache = ContextCompressionCache()
    item = _make_item(text="hello world")
    cfg = _make_llm_config()
    result = cache.compress_item(item=item, llm_config=cfg, target_tokens=1000)
    assert isinstance(result, str)


def test_compress_item_cache_miss_then_hit_same_result():
    cache = ContextCompressionCache()
    item = _make_item(text="hello world")
    cfg = _make_llm_config()
    first = cache.compress_item(item=item, llm_config=cfg, target_tokens=1000)
    second = cache.compress_item(item=item, llm_config=cfg, target_tokens=1000)
    assert first == second


def test_compress_item_cache_populated_after_first_call():
    cache = ContextCompressionCache()
    item = _make_item(text="hello world")
    cfg = _make_llm_config()
    assert len(cache.entries) == 0
    cache.compress_item(item=item, llm_config=cfg, target_tokens=1000)
    assert len(cache.entries) == 1


def test_compress_item_different_target_tokens_recompresses():
    cache = ContextCompressionCache()
    long_text = "y" * 10000
    item = _make_item(text=long_text)
    cfg = _make_llm_config()
    r1 = cache.compress_item(item=item, llm_config=cfg, target_tokens=10)
    r2 = cache.compress_item(item=item, llm_config=cfg, target_tokens=500)
    assert r1 != r2


def test_compress_item_changed_text_recompresses():
    cache = ContextCompressionCache()
    cfg = _make_llm_config()
    item1 = _make_item(text="original " * 2000)
    item2 = _make_item(text="changed " * 2000)
    r1 = cache.compress_item(item=item1, llm_config=cfg, target_tokens=10)
    r2 = cache.compress_item(item=item2, llm_config=cfg, target_tokens=10)
    assert r1 != r2
