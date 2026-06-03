"""
gossip_handler.py - Orchestrates one gossip tick over selected NPC pairs.

Does NOT: run global scheduling loops.

Dependencies injected: AsyncSession, Settings, GossipWeightConfig, EmbeddingIndex.
"""

from __future__ import annotations

import asyncio
import logging
import random

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.engines.embedding_invalidation import invalidate_embedding_safely
from npc_engine.engines.gossip.edge_updater import log_gossip
from npc_engine.engines.gossip.gossip_config import GossipWeightConfig
from npc_engine.engines.gossip.gossip_distort import gossip_distort
from npc_engine.engines.gossip.knowledge_propagator import (
    propagate,
    propagate_secret,
    SECRET_BASE_PROBABILITY,
    SECRET_DISTORTION_CHANCE,
)
from npc_engine.engines.gossip.pair_selector import select_pairs
from npc_engine.graph.rumor_service import believe_rumor, create_rumor
from npc_engine.retrieval.embedding_index import EmbeddingIndex

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from npc_engine.engines.emotion.emotion_updater import EmotionUpdater


LOGGER = logging.getLogger(__name__)


CYPHER_SELECT_EVENT = """
MATCH (a:Character {id: $sharer_id})-[k:KNOWS_ABOUT]->(e:Event)
WHERE coalesce(k.knowledge_state, '') <> 'corrected'
RETURN e.id AS event_id,
       e.summary AS summary,
       e.severity AS severity,
       coalesce(e.is_canonical, false) AS is_canonical
ORDER BY coalesce(e.is_canonical, false) DESC,
         e.occurred_at DESC
LIMIT 1
"""

CYPHER_RELATION_TRUST = """
MATCH (a:Character {id: $sharer_id})-[r:RELATES_TO]->(b:Character {id: $receiver_id})
RETURN r.trust AS trust
"""

CYPHER_SELECT_SECRET = """
MATCH (a:Character {id: $sharer_id})-[:KNOWS_SECRET]->(s:Secret)
RETURN s.id AS secret_id, s.severity AS severity
ORDER BY s.severity DESC
LIMIT 1
"""


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
        """Execute one gossip tick: select pairs, distort, propagate, log, invalidate.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick identifier.
            max_pairs: Maximum number of NPC pairs to process.
            npc_ids: Optional allowlist; only pairs containing at least one listed ID are processed.

        Returns:
            Dict with keys ``tick_id``, ``pairs`` (pairs evaluated), and ``propagated`` (successful propagations).
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
            propagated = 0
            for sharer, receiver, _loc, faction_ctx in pairs:
                event_result = await session.run(CYPHER_SELECT_EVENT, sharer_id=sharer["id"])
                event_record = await event_result.single()
                if event_record is None:
                    continue
                trust_result = await session.run(
                    CYPHER_RELATION_TRUST,
                    sharer_id=sharer["id"],
                    receiver_id=receiver["id"],
                )
                trust_record = await trust_result.single()
                trust = int(trust_record["trust"]) if trust_record is not None else 50
                best_standing: int | None = faction_ctx.get("best_standing")
                severity_int = int(event_record["severity"])
                distortion = gossip_distort(
                    event_summary=str(event_record["summary"]),
                    sharer_honesty=int(sharer.get("honesty", 50)),
                    sharer_receiver_trust=trust,
                    event_severity=severity_int,
                    tick_id=tick_id,
                    distortion_base=self._settings.GOSSIP_DISTORTION_BASE,
                    faction_standing=best_standing,
                    hostile_distortion_factor=self._weight_config.hostile_distortion_factor,
                    is_canonical=bool(event_record.get("is_canonical", False)),
                )
                event_id = str(event_record["event_id"])
                await propagate(
                    session=session,
                    receiver_id=receiver["id"],
                    source_character_id=sharer["id"],
                    event_id=event_id,
                    tick_id=tick_id,
                    distortion=distortion,
                )
                if distortion.distortion_level >= self._settings.RUMOR_DISTORTION_THRESHOLD:
                    try:
                        rumor_id = await create_rumor(
                            session,
                            content=distortion.summary,
                            origin_event_id=event_id,
                            created_at_tick=tick_id,
                            severity=severity_int,
                            is_fabricated=False,
                        )
                        await believe_rumor(
                            session,
                            character_id=receiver["id"],
                            rumor_id=rumor_id,
                            confidence=distortion.distortion_level,
                            tick=tick_id,
                            from_character_id=sharer["id"],
                        )
                    except Exception:
                        LOGGER.exception("Failed to record rumor for event %s", event_id)
                if (
                    self._emotion_updater is not None
                    and severity_int >= self._settings.RUMOR_EMOTION_SEVERITY_THRESHOLD
                ):
                    self._emotion_updater.apply_event_shock(
                        npc_id=receiver["id"],
                        severity=severity_int,
                    )
                    LOGGER.info(
                        "emotion_shock npc_id=%s severity=%d tick=%d",
                        receiver["id"],
                        severity_int,
                        tick_id,
                    )

                trust_delta = 1 if distortion.distortion_type is None else -1
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

                # Secret propagation: lower base probability, higher distortion.
                if random.random() < SECRET_BASE_PROBABILITY:
                    secret_result = await session.run(
                        CYPHER_SELECT_SECRET, sharer_id=sharer["id"]
                    )
                    secret_record = await secret_result.single()
                    if secret_record is not None:
                        distorted = random.random() < SECRET_DISTORTION_CHANCE
                        await propagate_secret(
                            session=session,
                            receiver_id=receiver["id"],
                            secret_id=str(secret_record["secret_id"]),
                            source_character_id=sharer["id"],
                            tick_id=tick_id,
                            distorted=distorted,
                        )

            return {"tick_id": tick_id, "pairs": len(pairs), "propagated": propagated}
