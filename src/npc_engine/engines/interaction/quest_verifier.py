"""
Module: quest_verifier
Layer: engines
Purpose: Graph-based verification that a player has satisfied quest objectives.
         The ``"deliver"`` verifier checks player inventory via OWNS edge;
         other objective types are registered as explicit stubs for future phases.
Does NOT: mutate quest state, call LLM, or issue HTTP requests.
Dependencies injected: AsyncSession (caller-managed).
Used by: engines.interaction.quest_handler, api.routes.interaction
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession

from npc_engine.engines.quest.models import QuestObjectiveInput

_logger = logging.getLogger(__name__)

_CYPHER_PLAYER_HAS_ITEM = """
MATCH (p:Character {id: $player_id})-[:OWNS]->(i:Item {id: $item_id})
RETURN count(i) AS qty
"""


class DeliverVerifier:
    """Verifies a ``"deliver"`` objective by checking the player's OWNS edge.

    Args:
        session: Active Neo4j async session.
    """

    async def verify(
        self,
        session: AsyncSession,
        player_id: str,
        objective: QuestObjectiveInput,
    ) -> bool:
        """Return True when the player owns at least target_count of the target item.

        Args:
            session: Active Neo4j async session.
            player_id: Character ID of the player.
            objective: Objective definition including target_id and target_count.

        Returns:
            True if the HAS_ITEM edge exists and quantity satisfies target_count.
        """
        if not objective.target_id:
            _logger.warning("deliver objective %s has no target_id — cannot verify", objective.objective_id)
            return False
        result = await session.run(
            _CYPHER_PLAYER_HAS_ITEM,
            player_id=player_id,
            item_id=objective.target_id,
        )
        record = await result.single()
        if record is None:
            return False
        return int(record["qty"]) >= objective.target_count


class _StubVerifier:
    """Placeholder verifier for objective types not yet implemented."""

    async def verify(
        self,
        session: AsyncSession,  # noqa: ARG002
        player_id: str,  # noqa: ARG002
        objective: QuestObjectiveInput,
    ) -> bool:
        """Always returns False — stub type not implemented."""
        _logger.info("stub verifier called for objective_type=%s — returning False", objective.objective_type)
        return False


_VERIFIERS: dict[str, object] = {
    "deliver": DeliverVerifier(),
    "kill": _StubVerifier(),
    "visit": _StubVerifier(),
    "talk": _StubVerifier(),
}


async def verify_objectives(
    session: AsyncSession,
    player_id: str,
    objectives: list[QuestObjectiveInput],
) -> bool:
    """Return True when all objectives are satisfied for the given player.

    Iterates objectives in order; short-circuits on the first unsatisfied one.

    Args:
        session: Active Neo4j async session.
        player_id: Character ID of the player being evaluated.
        objectives: List of objective definitions to verify.

    Returns:
        True when every objective is satisfied, False otherwise.
    """
    for obj in objectives:
        verifier = _VERIFIERS.get(obj.objective_type)
        if verifier is None:
            _logger.warning("no verifier registered for objective_type=%s", obj.objective_type)
            return False
        ok = await verifier.verify(session, player_id, obj)  # type: ignore[union-attr]
        if not ok:
            return False
    return True
