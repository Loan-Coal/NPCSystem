"""
context_compression.py - In-memory compression cache and deterministic text compression.

Does NOT: call external LLM services.

Dependencies injected: LLMConfig.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TypeAlias

from common.json_utils import parse_json_object
from retrieval.context_merger import ContextItem
from retrieval.context_utils import CHARS_PER_TOKEN_ESTIMATE, parse_node_identity
from schema.llm_config_models import LLMConfig


MIN_COMPRESSED_CHARS = 32
COMPRESSION_SUFFIX = "...[compressed]"

CompressionCacheKey: TypeAlias = tuple[str, str, str, str]


@dataclass(frozen=True)
class CompressionCacheEntry:
    """Cached compression output for one canonical cache key."""

    graph_timestamp: str | None
    source_hash: str
    target_tokens: int
    compressed_text: str


class ContextCompressionCache:
    """In-memory compression cache keyed by canonical node and prompt versions."""

    def __init__(self) -> None:
        """Initialise an empty compression cache."""

        self.entries: dict[CompressionCacheKey, CompressionCacheEntry] = {}

    def compress_item(self, *, item: ContextItem, llm_config: LLMConfig, target_tokens: int) -> str:
        """Compress one context item using deterministic local logic and cache.

        Args:
            item: The context item whose text should be compressed.
            llm_config: LLM configuration providing cache versioning fields.
            target_tokens: Desired token budget for the compressed output.

        Returns:
            Compressed text, returned from cache when the source has not changed.
        """

        node_type, node_id = parse_node_identity(item.key)
        key = build_compression_cache_key(
            node_id=node_id,
            node_type=node_type,
            prompt_schema_version=llm_config.prompt_schema_version,
            compression_prompt_version=llm_config.compression_prompt_version,
        )
        graph_timestamp = _extract_graph_timestamp(item.text)
        source_hash = hashlib.sha1(item.text.encode("utf-8")).hexdigest()
        cached = self.entries.get(key)
        if cached is not None and cached.target_tokens == target_tokens:
            if (
                graph_timestamp is not None
                and cached.graph_timestamp == graph_timestamp
                and cached.source_hash == source_hash
            ):
                return cached.compressed_text
            if graph_timestamp is None and cached.source_hash == source_hash:
                return cached.compressed_text

        compressed = _compress_text(item.text, target_tokens=target_tokens)
        self.entries[key] = CompressionCacheEntry(
            graph_timestamp=graph_timestamp,
            source_hash=source_hash,
            target_tokens=target_tokens,
            compressed_text=compressed,
        )
        return compressed


def build_compression_cache_key(
    *,
    node_id: str,
    node_type: str,
    prompt_schema_version: str,
    compression_prompt_version: str,
) -> CompressionCacheKey:
    """Build a canonical cache key from node identity and prompt versioning.

    Args:
        node_id: Unique identifier of the graph node.
        node_type: Type label of the graph node (e.g. ``Character``).
        prompt_schema_version: Version string from LLMConfig.
        compression_prompt_version: Compression prompt version string from LLMConfig.

    Returns:
        A 4-tuple used as the dict key in ContextCompressionCache.
    """

    return (
        node_id,
        node_type,
        prompt_schema_version,
        compression_prompt_version,
    )


def _compress_text(text: str, *, target_tokens: int) -> str:
    target_chars = max(MIN_COMPRESSED_CHARS, target_tokens * CHARS_PER_TOKEN_ESTIMATE)
    if len(text) <= target_chars:
        return text

    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    clipped = text[: max(1, target_chars - len(COMPRESSION_SUFFIX) - 12)]
    return f"{clipped}{COMPRESSION_SUFFIX}#{digest}"


def _extract_graph_timestamp(text: str) -> str | None:
    payload = parse_json_object(text)
    if len(payload) == 0:
        return None

    for field in ("last_graph_updated_at", "updated_at", "occurred_at", "created_at"):
        value = payload.get(field)
        if isinstance(value, str) and value != "":
            return value
    return None
