"""
context_compression.py - In-memory compression cache and deterministic text compression.
Layer: retrieval
Purpose: (auto-detected — review)

Does NOT: call external LLM services.

Dependencies injected: LLMConfig.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TypeAlias

from npc_engine.common.json_utils import parse_json_object
from npc_engine.retrieval.context_merger import ContextItem
from npc_engine.retrieval.context_utils import CHARS_PER_TOKEN_ESTIMATE, parse_node_identity
from npc_engine.schema.context_config_models import LLMConfig


MIN_COMPRESSED_CHARS = 32
COMPRESSION_SUFFIX = "...[compressed]"

CompressionCacheKey: TypeAlias = tuple[str, str, str, str]

# Essential fields to retain per node type when compressing.
# All other fields are dropped before the token-size check.
_ESSENTIAL_FIELDS: dict[str, frozenset[str]] = {
    "event": frozenset({"summary", "event_type", "severity", "occurred_at"}),
    "character": frozenset({"name", "archetype", "current_mood", "biography"}),
    "location": frozenset({"name", "descriptor", "region"}),
    "memory": frozenset({"content", "vividness", "emotional_charge"}),
    "belief": frozenset({"content", "confidence", "target_id"}),
    "goal": frozenset({"description", "urgency", "status", "target_id"}),
    "secret": frozenset({"content", "severity"}),
    "item": frozenset({"name", "item_type", "value", "rarity"}),
    "debt": frozenset({"amount", "reason", "due_by"}),
}


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
            Compressed text, returned from npc_engine.cache when the source has not changed.
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

        compressed = _field_select_compress(item.text, node_type=node_type, target_tokens=target_tokens)
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


def _field_select_compress(text: str, node_type: str, target_tokens: int) -> str:
    """Compress by projecting to essential fields, then fall back to byte truncation.

    Args:
        text: JSON text of the context item.
        node_type: Node type string used to look up essential fields.
        target_tokens: Desired output token budget.

    Returns:
        Compressed text string that is valid JSON or a truncated suffix string.
    """
    payload = parse_json_object(text)
    if not payload:
        return _compress_text(text, target_tokens=target_tokens)

    essential = _ESSENTIAL_FIELDS.get(node_type)
    if essential is not None:
        projected = {k: v for k, v in payload.items() if k in essential and v is not None}
    else:
        projected = {k: v for k, v in payload.items() if v is not None}

    projected_text = json.dumps(projected, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    target_chars = max(MIN_COMPRESSED_CHARS, target_tokens * CHARS_PER_TOKEN_ESTIMATE)
    if len(projected_text) <= target_chars:
        return projected_text

    return _compress_text(projected_text, target_tokens=target_tokens)


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
