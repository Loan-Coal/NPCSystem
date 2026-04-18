"""
gossip_handler.py - Orchestrates one gossip tick over selected NPC pairs.

Does NOT: run global scheduling loops.

Dependencies injected: AsyncSession, Settings, EmbeddingIndex.
"""

from neo4j import AsyncSession
import asyncio
import logging

from config import Settings
from engines.embedding_invalidation import invalidate_embedding_safely
from engines.gossip.edge_updater import log_gossip
from engines.gossip.gossip_distort import gossip_distort
from engines.gossip.knowledge_propagator import propagate
from engines.gossip.pair_selector import select_pairs
from retrieval.embedding_index import EmbeddingIndex


LOGGER = logging.getLogger(__name__)


CYPHER_SELECT_EVENT = """
MATCH (a:Character {id: $sharer_id})-[k:KNOWS_ABOUT]->(e:Event)
RETURN e.id AS event_id,
       e.summary AS summary,
       e.severity AS severity
ORDER BY e.occurred_at DESC
LIMIT 1
"""

CYPHER_RELATION_TRUST = """
MATCH (a:Character {id: $sharer_id})-[r:RELATES_TO]->(b:Character {id: $receiver_id})
RETURN r.trust AS trust
"""


class GossipHandler:
    """Coordinates gossip pair processing for one tick."""

    def __init__(self, settings: Settings, embedding_index: EmbeddingIndex):
        self._settings = settings
        self._embedding_index = embedding_index
        self._lock = asyncio.Lock()

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int,
        max_pairs: int = 20,
        npc_ids: list[str] | None = None,
    ) -> dict:
        """Execute deterministic gossip propagation for selected pairs."""

        async with self._lock:
            pairs = await select_pairs(session=session, max_pairs=max_pairs)
            if npc_ids:
                allowed = set(npc_ids)
                pairs = [pair for pair in pairs if pair[0]["id"] in allowed or pair[1]["id"] in allowed]
            propagated = 0
            for sharer, receiver, _loc in pairs:
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
                distortion = gossip_distort(
                    event_summary=str(event_record["summary"]),
                    sharer_honesty=int(sharer.get("honesty", 50)),
                    sharer_receiver_trust=trust,
                    event_severity=int(event_record["severity"]),
                    tick_id=tick_id,
                    distortion_base=self._settings.GOSSIP_DISTORTION_BASE,
                )
                await propagate(
                    session=session,
                    receiver_id=receiver["id"],
                    source_character_id=sharer["id"],
                    event_id=str(event_record["event_id"]),
                    tick_id=tick_id,
                    distortion=distortion,
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
            return {"tick_id": tick_id, "pairs": len(pairs), "propagated": propagated}
