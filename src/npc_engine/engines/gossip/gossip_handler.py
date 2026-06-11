"""
gossip_handler.py - Orchestrates one gossip tick over selected NPC pairs.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: run global scheduling loops.

Dependencies injected: AsyncSession, Settings, GossipWeightConfig, EmbeddingIndex.

NOTE: This file is ~351 lines, over the 300-line soft limit. Splitting would
be artificial because run_tick + _process_pairs + _build_write_params + _run_side_effects
are all tightly coupled phases of a single orchestration class. Splitting would
scatter the gossip tick logic across multiple files with no independent reuse value.
See DEC-061 in project-harness/DECISIONS.md.
"""

from __future__ import annotations

import asyncio
import hashlib
import random

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.engines.embedding_invalidation import invalidate_embedding_safely
from npc_engine.engines.gossip.edge_updater import log_gossip
from npc_engine.engines.gossip.gossip_config import GossipWeightConfig
from npc_engine.engines.gossip.gossip_distort import (
    compute_confidence,
    compute_distortion_probability,
    compute_seed_value,
    gossip_distort,
)
from npc_engine.engines.gossip.knowledge_propagator import (
    propagate_secret,
    SECRET_BASE_PROBABILITY,
    SECRET_DISTORTION_CHANCE,
)
from npc_engine.graph.gossip_batch_queries import (
    select_batch_event_trust,
    select_gossip_secret,
    write_batch_knowledge_propagation,
)
from npc_engine.graph.rumor_service import believe_rumor, create_rumor
from npc_engine.engines.gossip.pair_selector import select_pairs
from npc_engine.retrieval.embedding_index import EmbeddingIndex
from npc_engine.utils.logging import get_logger

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from npc_engine.engines.emotion.emotion_updater import EmotionUpdater


LOGGER = get_logger(__name__)

_SECRET_SEED_NAMESPACE = "gossip_secret"


def _secret_rng_seed(sharer_id: str, receiver_id: str, tick_id: int) -> int:
    """Derive a deterministic integer seed for secret-propagation RNG.

    Args:
        sharer_id: ID of the NPC sharing the secret.
        receiver_id: ID of the NPC receiving the secret.
        tick_id: Current game tick.

    Returns:
        A 64-bit integer seed suitable for ``random.Random(seed)``.
    """
    raw = f"{_SECRET_SEED_NAMESPACE}|{sharer_id}|{receiver_id}|{tick_id}"
    return int.from_bytes(hashlib.sha256(raw.encode()).digest()[:8], byteorder="little")


class GossipHandler:
    """Coordinates gossip pair processing for one tick."""

    def __init__(
        self,
        settings: Settings,
        embedding_index: EmbeddingIndex,
        weight_config: GossipWeightConfig,
        emotion_updater: EmotionUpdater | None = None,
    ) -> None:
        """Initialise the gossip handler.

        Args:
            settings: Application settings (GOSSIP_DISTORTION_BASE, RUMOR_EMOTION_SEVERITY_THRESHOLD).
            embedding_index: Vector index used to invalidate receiver embeddings after gossip.
            weight_config: Faction weight multipliers for pair selection and distortion.
            emotion_updater: Optional emotion updater; when supplied, receivers of high-severity
                events have their emotion state shocked toward agitated/melancholic.
        """

        self._settings = settings
        self._embedding_index = embedding_index
        self._weight_config = weight_config
        self._emotion_updater = emotion_updater
        self._lock = asyncio.Lock()

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int,
        max_pairs: int = 20,
        npc_ids: list[str] | None = None,
    ) -> dict:
        """Execute one gossip tick: select pairs, batch-read events+trust, distort, batch-write.

        Replaces the previous N×3 sequential Neo4j round-trips with a single batch
        read (event + trust for all pairs) and a single batch write (all propagations).
        Conditional operations (log_gossip, rumor creation, emotion shock, secret
        propagation) still run per-pair after the batch write.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick identifier.
            max_pairs: Maximum number of NPC pairs to process.
            npc_ids: Optional allowlist; only pairs containing at least one listed ID are processed.

        Returns:
            Dict with keys ``tick_id``, ``pairs`` (pairs evaluated), ``propagated``
            (successful propagations), and ``seeds_used`` (mapping of
            ``"sharer_id→receiver_id"`` to the deterministic seed used for that pair).
        """

        async with self._lock:
            pairs = await select_pairs(
                session=session,
                max_pairs=max_pairs,
                weight_config=self._weight_config,
            )
            if npc_ids:
                allowed = set(npc_ids)
                pairs = [pair for pair in pairs if pair[0]["id"] in allowed or pair[1]["id"] in allowed]

            return await self._process_pairs(session=session, pairs=pairs, tick_id=tick_id)

    async def _process_pairs(
        self,
        session: AsyncSession,
        pairs: list,
        tick_id: int,
    ) -> dict:
        """Batch-read event+trust, compute distortions, batch-write, then run per-pair side effects.

        Args:
            session: Active Neo4j async session.
            pairs: List of (sharer, receiver, loc, faction_ctx) tuples from pair_selector.
            tick_id: Current game tick.

        Returns:
            Dict with keys ``tick_id``, ``pairs``, ``propagated``, and ``seeds_used``.
        """
        # Build pair lookup and params for the batch read query.
        pair_lookup: dict[tuple[str, str], tuple[dict, dict, dict]] = {}
        pair_params: list[dict[str, str]] = []
        for sharer, receiver, _loc, faction_ctx in pairs:
            key = (sharer["id"], receiver["id"])
            pair_lookup[key] = (sharer, receiver, faction_ctx)
            pair_params.append({"sharer_id": sharer["id"], "receiver_id": receiver["id"]})

        # 1 batched graph read (via select_batch_event_trust): event + trust for all pairs.
        batch_rows = await select_batch_event_trust(session, pairs=pair_params)
        event_trust_map: dict[tuple[str, str], dict] = {
            (row["sharer_id"], row["receiver_id"]): row
            for row in batch_rows
        }

        # Python-side: compute distortions for all pairs with a qualifying event.
        write_params, distortion_map, seeds_used = self._build_write_params(
            pair_lookup=pair_lookup,
            event_trust_map=event_trust_map,
            tick_id=tick_id,
        )

        # 1 batched graph write (via write_batch_knowledge_propagation): one UNWIND MERGE.
        await write_batch_knowledge_propagation(session, writes=write_params)

        # Conditional per-pair side effects (rumor, emotion, log, embedding invalidation).
        propagated = await self._run_side_effects(
            session=session,
            pair_lookup=pair_lookup,
            event_trust_map=event_trust_map,
            distortion_map=distortion_map,
            tick_id=tick_id,
        )

        return {
            "tick_id": tick_id,
            "pairs": len(pairs),
            "propagated": propagated,
            "seeds_used": seeds_used,
        }

    def _build_write_params(
        self,
        pair_lookup: dict[tuple[str, str], tuple[dict, dict, dict]],
        event_trust_map: dict[tuple[str, str], dict],
        tick_id: int,
    ) -> tuple[list[dict], dict[tuple[str, str], dict], dict[str, int]]:
        """Compute per-pair distortions and assemble batch write parameters.

        Args:
            pair_lookup: Mapping of (sharer_id, receiver_id) → (sharer, receiver, faction_ctx).
            event_trust_map: Mapping of (sharer_id, receiver_id) → event+trust row.
            tick_id: Current game tick.

        Returns:
            Tuple of (write_params list, distortion_map dict keyed by (sharer_id, receiver_id),
            seeds_used dict keyed by ``"sharer_id→receiver_id"``).
        """
        write_params: list[dict] = []
        distortion_map: dict[tuple[str, str], dict] = {}
        seeds_used: dict[str, int] = {}

        for key, (sharer, receiver, faction_ctx) in pair_lookup.items():
            row = event_trust_map.get(key)
            if row is None:
                continue

            trust = int(row["trust"])
            best_standing: int | None = faction_ctx.get("best_standing")
            severity_int = int(row["severity"])
            honesty_int = int(sharer.get("honesty", 50))

            distortion_probability = compute_distortion_probability(
                honesty=honesty_int,
                trust=trust,
                severity=severity_int,
                base=self._settings.GOSSIP_DISTORTION_BASE,
            )
            seed = compute_seed_value(
                summary=str(row["summary"]),
                honesty=honesty_int,
                trust=trust,
                tick_id=tick_id,
            )
            pair_key = f"{sharer['id']}→{receiver['id']}"
            seeds_used[pair_key] = seed
            LOGGER.debug(
                "gossip_pair sharer=%s receiver=%s tick=%d "
                "distortion_probability=%.3f seed=%d",
                sharer["id"],
                receiver["id"],
                tick_id,
                distortion_probability,
                seed,
            )

            # Compute belief_confidence before gossip_distort so it can bias
            # distortion-type selection (EXP-213: receiver_confidence kwarg).
            belief_confidence = compute_confidence(
                source_trust=trust, event_severity=severity_int
            )
            distortion = gossip_distort(
                event_summary=str(row["summary"]),
                sharer_honesty=honesty_int,
                sharer_receiver_trust=trust,
                event_severity=severity_int,
                tick_id=tick_id,
                distortion_base=self._settings.GOSSIP_DISTORTION_BASE,
                faction_standing=best_standing,
                hostile_distortion_factor=self._weight_config.hostile_distortion_factor,
                is_canonical=bool(row.get("is_canonical", False)),
                receiver_confidence=belief_confidence,
                confidence_high_threshold=self._weight_config.confidence_high_threshold,
                confidence_low_threshold=self._weight_config.confidence_low_threshold,
            )
            knowledge_state = "knows" if distortion.distortion_type is None else "rumor"
            write_entry: dict = {
                "receiver_id": receiver["id"],
                "event_id": str(row["event_id"]),
                "knowledge_state": knowledge_state,
                "distortion_type": distortion.distortion_type,
                "distortion_level": distortion.distortion_level,
                "distorted_summary": distortion.summary,
                "tick_id": tick_id,
                "source_character_id": sharer["id"],
                "belief_confidence": belief_confidence,
            }
            write_params.append(write_entry)
            distortion_map[key] = write_entry

        return write_params, distortion_map, seeds_used

    async def _run_side_effects(
        self,
        session: AsyncSession,
        pair_lookup: dict[tuple[str, str], tuple[dict, dict, dict]],
        event_trust_map: dict[tuple[str, str], dict],
        distortion_map: dict[tuple[str, str], dict],
        tick_id: int,
    ) -> int:
        """Run conditional per-pair side effects after the batch write.

        Side effects: rumor creation, emotion shock, relation-log update,
        embedding invalidation, and secret propagation.

        Args:
            session: Active Neo4j async session.
            pair_lookup: Mapping of (sharer_id, receiver_id) → (sharer, receiver, faction_ctx).
            event_trust_map: Mapping of (sharer_id, receiver_id) → event+trust row.
            distortion_map: Mapping of (sharer_id, receiver_id) → write params dict.
            tick_id: Current game tick.

        Returns:
            Number of pairs successfully propagated.
        """
        propagated = 0
        for key, write in distortion_map.items():
            sharer, receiver, _faction_ctx = pair_lookup[key]
            row = event_trust_map[key]
            severity_int = int(row["severity"])
            event_id = write["event_id"]

            if write["distortion_level"] >= self._settings.RUMOR_DISTORTION_THRESHOLD:
                try:
                    rumor_id = await create_rumor(
                        session,
                        content=write["distorted_summary"],
                        origin_event_id=event_id,
                        created_at_tick=tick_id,
                        severity=severity_int,
                        is_fabricated=False,
                    )
                    await believe_rumor(
                        session,
                        character_id=receiver["id"],
                        rumor_id=rumor_id,
                        confidence=write["belief_confidence"],
                        tick=tick_id,
                        from_character_id=sharer["id"],
                    )
                except Exception:
                    LOGGER.exception("Failed to record rumor for event %s", event_id)
                    raise

            if (
                self._emotion_updater is not None
                and severity_int >= self._settings.RUMOR_EMOTION_SEVERITY_THRESHOLD
            ):
                await self._emotion_updater.apply_event_shock(
                    npc_id=receiver["id"],
                    severity=severity_int,
                )
                LOGGER.info(
                    "emotion_shock npc_id=%s severity=%d tick=%d",
                    receiver["id"],
                    severity_int,
                    tick_id,
                )

            trust_delta = 1 if write["distortion_type"] is None else -1
            await log_gossip(
                session=session,
                src_id=sharer["id"],
                dst_id=receiver["id"],
                tick_id=tick_id,
                trust_delta=trust_delta,
            )
            await invalidate_embedding_safely(
                embedding_index=self._embedding_index,
                item_id=receiver["id"],
                logger=LOGGER,
                entity_label="receiver",
            )
            propagated += 1

            # Secret propagation: lower base probability, higher distortion chance.
            secret_seed = _secret_rng_seed(sharer["id"], receiver["id"], tick_id)
            LOGGER.debug(
                "gossip_secret_rng seed=%d sharer=%s receiver=%s tick=%d",
                secret_seed, sharer["id"], receiver["id"], tick_id,
            )
            rng = random.Random(secret_seed)
            if rng.random() < SECRET_BASE_PROBABILITY:
                secret_record = await select_gossip_secret(session, sharer_id=sharer["id"])
                if secret_record is not None:
                    distorted = rng.random() < SECRET_DISTORTION_CHANCE
                    await propagate_secret(
                        session=session,
                        receiver_id=receiver["id"],
                        secret_id=str(secret_record["secret_id"]),
                        source_character_id=sharer["id"],
                        tick_id=tick_id,
                        distorted=distorted,
                    )

        return propagated
