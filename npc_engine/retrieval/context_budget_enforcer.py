"""
context_budget_enforcer.py - Tier-aware context budget enforcement with compression cache.

Does NOT: call external LLM services for compression.

Dependencies injected: LLMConfig.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import TypeAlias

from common.json_utils import parse_json_object
from retrieval.context_merger import ContextItem, MergedContext
from retrieval.context_utils import CHARS_PER_TOKEN_ESTIMATE, estimate_tokens, parse_node_identity
from schema.llm_config_models import LLMConfig


MIN_COMPRESSED_CHARS = 32
COMPRESSION_SUFFIX = "...[compressed]"

CompressionCacheKey: TypeAlias = tuple[str, str, str, str]


@dataclass(frozen=True)
class ContextBudgetError(Exception):
    """Typed budget error for tier-specific overflow diagnostics."""

    tier: str
    used_tokens: int
    budget_tokens: int
    detail: str

    def __str__(self) -> str:
        return (
            "ContextBudgetError("
            f"tier={self.tier}, used_tokens={self.used_tokens}, "
            f"budget_tokens={self.budget_tokens}, detail={self.detail})"
        )


@dataclass(frozen=True)
class CompressionCacheEntry:
    """Cached compression output for one canonical cache key."""

    graph_timestamp: str | None
    source_hash: str
    target_tokens: int
    compressed_text: str


class ContextCompressionCache:
    """In-memory compression cache keyed by canonical node and prompt versions."""

    def __init__(self):
        self.entries: dict[CompressionCacheKey, CompressionCacheEntry] = {}

    def compress_item(self, *, item: ContextItem, llm_config: LLMConfig, target_tokens: int) -> str:
        """Compress one context item using deterministic local logic and cache."""

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
    """Build cache key from canonical dimensions required by the v1.4 plan."""

    return (
        node_id,
        node_type,
        prompt_schema_version,
        compression_prompt_version,
    )


def enforce_context_budget(
    *,
    context: MergedContext,
    llm_config: LLMConfig,
    compression_cache: ContextCompressionCache | None = None,
) -> MergedContext:
    """Apply tier-aware budget policy with compression for compressible tiers only."""

    cache = compression_cache or ContextCompressionCache()

    tier0_items = [item for item in context.items if item.tier == "tier0"]
    tier_a_items = [item for item in context.items if item.tier == "tierA"]
    tier_b_items = [item for item in context.items if item.tier == "tierB"]
    tier_c_items = [item for item in context.items if item.tier == "tierC"]

    tier_a_tokens = sum(estimate_tokens(item.text) for item in tier_a_items)
    tier_a_budget = llm_config.tier_budget_tokens.tier_a
    if tier_a_tokens > tier_a_budget:
        raise ContextBudgetError(
            tier="tier_a",
            used_tokens=tier_a_tokens,
            budget_tokens=tier_a_budget,
            detail="Tier A exceeds configured budget and is non-compressible.",
        )

    session_items = [item for item in tier_a_items if item.key == "session"]
    session_tokens = sum(estimate_tokens(item.text) for item in session_items)
    if session_tokens > llm_config.session_turns_budget_tokens:
        raise ContextBudgetError(
            tier="session_turns",
            used_tokens=session_tokens,
            budget_tokens=llm_config.session_turns_budget_tokens,
            detail="Session turns exceed Tier A sub-budget and are non-compressible.",
        )

    tier_b_fitted = _fit_compressible_tier(
        tier_name="tier_b",
        items=tier_b_items,
        budget_tokens=llm_config.tier_budget_tokens.tier_b,
        llm_config=llm_config,
        cache=cache,
    )
    tier_c_fitted = _fit_compressible_tier(
        tier_name="tier_c",
        items=tier_c_items,
        budget_tokens=llm_config.tier_budget_tokens.tier_c,
        llm_config=llm_config,
        cache=cache,
    )

    return MergedContext(items=[*tier0_items, *tier_a_items, *tier_b_fitted, *tier_c_fitted])


def _fit_compressible_tier(
    *,
    tier_name: str,
    items: list[ContextItem],
    budget_tokens: int,
    llm_config: LLMConfig,
    cache: ContextCompressionCache,
) -> list[ContextItem]:
    if len(items) == 0:
        return []

    used_tokens = sum(estimate_tokens(item.text) for item in items)
    if used_tokens <= budget_tokens and used_tokens <= int(budget_tokens * llm_config.compression_trigger_ratio):
        return items

    per_item_target = max(1, budget_tokens // len(items))
    compressed_items = [
        item.model_copy(
            update={
                "text": cache.compress_item(item=item, llm_config=llm_config, target_tokens=per_item_target),
            }
        )
        for item in items
    ]

    fitted = sorted(compressed_items, key=lambda item: (-item.priority, item.key))
    total_tokens = sum(estimate_tokens(item.text) for item in fitted)

    while total_tokens > budget_tokens and len(fitted) > 0:
        dropped = fitted.pop()
        total_tokens -= estimate_tokens(dropped.text)

    if total_tokens > budget_tokens:
        raise ContextBudgetError(
            tier=tier_name,
            used_tokens=total_tokens,
            budget_tokens=budget_tokens,
            detail="Tier exceeds budget after compression.",
        )

    return fitted

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
