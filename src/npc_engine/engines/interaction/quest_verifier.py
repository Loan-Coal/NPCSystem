"""
Module: quest_verifier
Layer: engines
Purpose: Graph-based verification that a player has satisfied quest objectives.
Does NOT: mutate quest state, call LLM, issue HTTP requests, or hold a Neo4j session.
Dependencies injected: InteractionGraphPort (read-only objective counters).
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
from typing import TYPE_CHECKING

from npc_engine.engines.quest.models import QuestObjectiveInput

if TYPE_CHECKING:
    from npc_engine.engines.ports.interaction_port import InteractionGraphPort

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verifier classes
# ---------------------------------------------------------------------------


class DeliverVerifier:
    """Verifies a ``"deliver"`` objective by checking the player's OWNS edge."""

    async def verify(
        self,
        repo: InteractionGraphPort,
        player_id: str,
        objective: QuestObjectiveInput,
    ) -> bool:
        """Return True when the player owns at least target_count of the target item.

        Args:
            repo: Interaction graph read port.
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
        cnt = await repo.count_player_has_item(player_id=player_id, item_id=objective.target_id)
        return cnt >= objective.target_count


class VisitVerifier:
    """Verifies a ``"visit"`` objective.

    Satisfied when the player is currently LOCATED_AT the target location,
    or has a historical WAS_AT edge to it.
    """

    async def verify(
        self,
        repo: InteractionGraphPort,
        player_id: str,
        objective: QuestObjectiveInput,
    ) -> bool:
        """Return True when the player has been at the target location.

        Args:
            repo: Interaction graph read port.
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
        current = await repo.count_player_located_at(player_id=player_id, location_id=objective.target_id)
        if current >= 1:
            return True
        historical = await repo.count_player_was_at(player_id=player_id, location_id=objective.target_id)
        return historical >= 1


class KillVerifier:
    """Verifies a ``"kill"`` objective.

    Satisfied when the target Character node has ``is_active=False``.
    ``is_active`` is the graph's death proxy; no dedicated KILLED edge exists.
    """

    async def verify(
        self,
        repo: InteractionGraphPort,
        player_id: str,  # noqa: ARG002
        objective: QuestObjectiveInput,
    ) -> bool:
        """Return True when the target character is inactive (dead).

        Args:
            repo: Interaction graph read port.
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
        cnt = await repo.count_target_inactive(target_id=objective.target_id)
        return cnt >= 1


class TalkVerifier:
    """Verifies a ``"talk"`` objective via co-location proxy.

    Satisfied when the player and the target NPC are both LOCATED_AT the same
    Location node. This is a co-location proxy — no SPOKE_TO edge exists in the
    schema. See DECISIONS.md DEC-043 for the rationale and future upgrade path.
    """

    async def verify(
        self,
        repo: InteractionGraphPort,
        player_id: str,
        objective: QuestObjectiveInput,
    ) -> bool:
        """Return True when the player is co-located with the target NPC.

        Args:
            repo: Interaction graph read port.
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
        cnt = await repo.count_player_co_located_with(player_id=player_id, target_id=objective.target_id)
        return cnt >= 1


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
    repo: InteractionGraphPort,
    player_id: str,
    objectives: list[QuestObjectiveInput],
) -> bool:
    """Return True when all objectives are satisfied for the given player.

    Iterates objectives in order; short-circuits on the first unsatisfied one.

    Args:
        repo: Interaction graph read port.
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
        ok = await verifier.verify(repo, player_id, obj)
        if not ok:
            return False
    return True
