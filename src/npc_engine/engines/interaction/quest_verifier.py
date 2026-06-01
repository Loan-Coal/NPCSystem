"""
Module: quest_verifier
Layer: engines
Purpose: Graph-based verification that a player has satisfied quest objectives.
Does NOT: mutate quest state, call LLM, or issue HTTP requests.
Dependencies injected: AsyncSession (caller-managed).
Used by: engines.interaction.quest_handler, api.routes.interaction

Verifier semantics
------------------
deliver  — player OWNS the required item (HAS_ITEM edge).
visit    — player is currently LOCATED_AT, OR has a WAS_AT edge for, the target location.
kill     — target Character has is_active=False (death proxy; no dedicated KILLED edge exists).
talk     — player and target NPC are both LOCATED_AT the same Location (co-location proxy;
           no SPOKE_TO edge exists — see DECISIONS.md DEC-043).
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession

from npc_engine.engines.quest.models import QuestObjectiveInput

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

_CYPHER_PLAYER_HAS_ITEM = """
MATCH (p:Character {id: $player_id})-[:OWNS]->(i:Item {id: $item_id})
RETURN count(i) AS cnt
"""

_CYPHER_PLAYER_LOCATED_AT = """
MATCH (p:Character {id: $player_id})-[:LOCATED_AT]->(l:Location {id: $location_id})
RETURN count(l) AS cnt
"""

_CYPHER_PLAYER_WAS_AT = """
MATCH (p:Character {id: $player_id})-[:WAS_AT]->(l:Location {id: $location_id})
RETURN count(l) AS cnt
"""

_CYPHER_TARGET_INACTIVE = """
MATCH (c:Character {id: $target_id})
WHERE c.is_active = false
RETURN count(c) AS cnt
"""

_CYPHER_PLAYER_CO_LOCATED_WITH = """
MATCH (p:Character {id: $player_id})-[:LOCATED_AT]->(loc:Location)<-[:LOCATED_AT]-(t:Character {id: $target_id})
RETURN count(loc) AS cnt
"""

_MIN_COUNT = 1


# ---------------------------------------------------------------------------
# Verifier classes
# ---------------------------------------------------------------------------


class DeliverVerifier:
    """Verifies a ``"deliver"`` objective by checking the player's OWNS edge."""

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
            True if the OWNS edge exists and quantity satisfies target_count.
        """
        if not objective.target_id:
            _logger.warning(
                "deliver objective %s has no target_id — cannot verify",
                objective.objective_id,
            )
            return False
        result = await session.run(
            _CYPHER_PLAYER_HAS_ITEM,
            player_id=player_id,
            item_id=objective.target_id,
        )
        record = await result.single()
        if record is None:
            return False
        return int(record["cnt"]) >= objective.target_count


class VisitVerifier:
    """Verifies a ``"visit"`` objective.

    Satisfied when the player is currently LOCATED_AT the target location,
    or has a historical WAS_AT edge to it.

    Args:
        session: Active Neo4j async session.
    """

    async def verify(
        self,
        session: AsyncSession,
        player_id: str,
        objective: QuestObjectiveInput,
    ) -> bool:
        """Return True when the player has been at the target location.

        Args:
            session: Active Neo4j async session.
            player_id: Character ID of the player.
            objective: Objective definition; target_id must be a Location node ID.

        Returns:
            True if the player is currently at or has previously visited the location.
        """
        if not objective.target_id:
            _logger.warning(
                "visit objective %s has no target_id — cannot verify",
                objective.objective_id,
            )
            return False
        current_result = await session.run(
            _CYPHER_PLAYER_LOCATED_AT,
            player_id=player_id,
            location_id=objective.target_id,
        )
        current_record = await current_result.single()
        if current_record is not None and int(current_record["cnt"]) >= _MIN_COUNT:
            return True
        historical_result = await session.run(
            _CYPHER_PLAYER_WAS_AT,
            player_id=player_id,
            location_id=objective.target_id,
        )
        historical_record = await historical_result.single()
        if historical_record is None:
            return False
        return int(historical_record["cnt"]) >= _MIN_COUNT


class KillVerifier:
    """Verifies a ``"kill"`` objective.

    Satisfied when the target Character node has ``is_active=False``.
    ``is_active`` is the graph's death proxy; no dedicated KILLED edge exists.

    Args:
        session: Active Neo4j async session.
    """

    async def verify(
        self,
        session: AsyncSession,
        player_id: str,  # noqa: ARG002
        objective: QuestObjectiveInput,
    ) -> bool:
        """Return True when the target character is inactive (dead).

        Args:
            session: Active Neo4j async session.
            player_id: Unused — kill verification is target-state only.
            objective: Objective definition; target_id must be a Character node ID.

        Returns:
            True if the target Character has is_active=False.
        """
        if not objective.target_id:
            _logger.warning(
                "kill objective %s has no target_id — cannot verify",
                objective.objective_id,
            )
            return False
        result = await session.run(
            _CYPHER_TARGET_INACTIVE,
            target_id=objective.target_id,
        )
        record = await result.single()
        if record is None:
            return False
        return int(record["cnt"]) >= _MIN_COUNT


class TalkVerifier:
    """Verifies a ``"talk"`` objective via co-location proxy.

    Satisfied when the player and the target NPC are both LOCATED_AT the same
    Location node. This is a co-location proxy — no SPOKE_TO edge exists in the
    schema. See DECISIONS.md DEC-043 for the rationale and future upgrade path.

    Args:
        session: Active Neo4j async session.
    """

    async def verify(
        self,
        session: AsyncSession,
        player_id: str,
        objective: QuestObjectiveInput,
    ) -> bool:
        """Return True when the player is co-located with the target NPC.

        Args:
            session: Active Neo4j async session.
            player_id: Character ID of the player.
            objective: Objective definition; target_id must be a Character node ID.

        Returns:
            True if player and target share a LOCATED_AT location.
        """
        if not objective.target_id:
            _logger.warning(
                "talk objective %s has no target_id — cannot verify",
                objective.objective_id,
            )
            return False
        result = await session.run(
            _CYPHER_PLAYER_CO_LOCATED_WITH,
            player_id=player_id,
            target_id=objective.target_id,
        )
        record = await result.single()
        if record is None:
            return False
        return int(record["cnt"]) >= _MIN_COUNT


# ---------------------------------------------------------------------------
# Verifier registry
# ---------------------------------------------------------------------------

_VERIFIERS: dict[str, DeliverVerifier | VisitVerifier | KillVerifier | TalkVerifier] = {
    "deliver": DeliverVerifier(),
    "kill": KillVerifier(),
    "visit": VisitVerifier(),
    "talk": TalkVerifier(),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
        ok = await verifier.verify(session, player_id, obj)
        if not ok:
            return False
    return True
