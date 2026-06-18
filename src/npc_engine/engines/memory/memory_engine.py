"""
Module: memory_engine
Layer: engines
Purpose: Rules-based engine for forming memories from high-arousal moments, commitment
    events, running daily vividness decay, computing memory salience, and deciding
    forgettability (EXP-212, EXP-214).
Does NOT: query or persist state directly — all I/O is delegated to a MemoryGraphPort.
Dependencies: engines.ports.memory_port, world.time_utils
Dependencies injected: MemoryGraphPort (via __init__; DEC-122 / SEV-24 — no session).
Used by: engines.dialogue.dialogue_handler, api.routes.clock,
         engines.quest.quest_lifecycle_engine
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from npc_engine.world.time_utils import TimePoint

if TYPE_CHECKING:
    from npc_engine.engines.ports.memory_port import MemoryGraphPort

# ---------------------------------------------------------------------------
# Memory kind constants (DEC-100 — values must match memory.yaml schema).
# ---------------------------------------------------------------------------

MEMORY_KIND_EPISODIC: str = "episodic"
MEMORY_KIND_COMMITMENT: str = "commitment"
MEMORY_KIND_FACT: str = "fact"

# ---------------------------------------------------------------------------
# Arousal / semantic formation thresholds
# ---------------------------------------------------------------------------

_HIGH_AROUSAL_THRESHOLD = 70
_HIGH_AROUSAL_VIVIDNESS = 80
_COMMITMENT_VIVIDNESS = 100
_COMMITMENT_EMOTIONAL_CHARGE = 50
_DECAY_BASE_RATE = 5
_DECAY_CHARGE_DIVISOR = 20
_SEMANTIC_VIVIDNESS = 60
_SEMANTIC_KEYWORDS: tuple[str, ...] = (
    "death",
    "betrayal",
    "war",
    "assassination",
    "plague",
    "execution",
    "exile",
    "coup",
)

# Salience component weights — must sum to 1.0.
_SALIENCE_VIVIDNESS_WEIGHT: float = 0.4
_SALIENCE_CHARGE_WEIGHT: float = 0.4
_SALIENCE_RECALL_WEIGHT: float = 0.2

# Cap used when normalising recall_count to a 0-100 scale.
_RECALL_COUNT_SATURATION: int = 10


def compute_salience(
    *,
    vividness: int,
    emotional_charge: int,
    recall_count: int,
) -> float:
    """Compute a salience score (0–100) for a memory node.

    Salience combines vividness (40 %), absolute emotional charge (40 %),
    and recall_count normalised to a 0–100 scale capped at
    ``_RECALL_COUNT_SATURATION`` (20 %).  Higher salience = more memorable.

    Args:
        vividness: Current vividness value (0–100).
        emotional_charge: Emotional intensity.  Accepts negative values; only
            magnitude is used so pain and joy contribute equally.
        recall_count: How many times the memory has been recalled (0+).

    Returns:
        Float salience score in [0.0, 100.0].
    """
    normalised_charge = min(100, abs(emotional_charge))
    normalised_recall = min(100, (recall_count / _RECALL_COUNT_SATURATION) * 100)
    return (
        _SALIENCE_VIVIDNESS_WEIGHT * vividness
        + _SALIENCE_CHARGE_WEIGHT * normalised_charge
        + _SALIENCE_RECALL_WEIGHT * normalised_recall
    )


def is_forgettable(
    *,
    salience: float,
    never_forget: bool,
    threshold: float,
) -> bool:
    """Return True when a memory qualifies for scheduled forgetting.

    A memory is forgettable only when its salience is below ``threshold``
    AND ``never_forget`` is False.  Pinned memories (``never_forget=True``)
    are never forgettable regardless of salience.

    Args:
        salience: Pre-computed salience score (use ``compute_salience``).
        never_forget: When True the memory is permanently pinned.
        threshold: The ``MEMORY_FORGET_THRESHOLD`` value from settings.

    Returns:
        True when the memory should be scheduled for decay/deletion.
    """
    if never_forget:
        return False
    return salience < threshold


class MemoryEngine:
    """Rules-based engine for memory formation and vividness decay.

    Memory formation triggers when NPC arousal exceeds the high-arousal
    threshold after a dialogue exchange. Vividness decay runs once per
    day advance, reducing all memory vividness by a fixed amount.

    Persistence is delegated to an injected MemoryGraphPort; the engine holds
    no Neo4j session (DEC-122 / SEV-24).
    """

    def __init__(self, memory_repo: MemoryGraphPort) -> None:
        """Initialise with the memory persistence port.

        Args:
            memory_repo: Graph adapter implementing create_memory + the two decays.
        """
        self._repo = memory_repo

    async def create_from_arousal(
        self,
        *,
        character_id: str,
        arousal: int,
        content: str,
        game_time: TimePoint,
        player_id: str | None = None,
    ) -> str | None:
        """Create a memory if arousal exceeds the high-arousal threshold.

        When ``player_id`` is supplied the memory is tagged with
        ``subject_player_id`` so it can be retrieved via player-scoped
        queries (EXP-211).

        Args:
            character_id: ID of the NPC who formed the memory.
            arousal: Current arousal level (0–100).
            content: Description of the memorable moment.
            game_time: Game-time snapshot at moment of formation.
            player_id: Optional player whose interaction triggered this
                memory.  Stored as ``subject_player_id`` on the node.

        Returns:
            Memory ID string if a memory was created, else None.
        """
        if arousal <= _HIGH_AROUSAL_THRESHOLD:
            return None
        return await self._repo.create_memory(
            character_id=character_id,
            content=content,
            vividness=_HIGH_AROUSAL_VIVIDNESS,
            emotional_charge=min(100, arousal - 50),
            game_time=game_time,
            subject_player_id=player_id,
        )

    async def create_from_commitment(
        self,
        *,
        character_id: str,
        content: str,
        game_time: TimePoint,
        player_id: str | None = None,
    ) -> str:
        """Create a commitment memory for a promise made between NPC and player.

        Commitment memories are always formed at maximum vividness and tagged with
        ``kind=MEMORY_KIND_COMMITMENT`` so they can be recalled distinctly from
        arousal-formed episodic memories.  They are never gated by an arousal
        threshold — any quiet promise is remembered.

        Args:
            character_id: ID of the NPC who witnessed / made the commitment.
            content: Description of the promise or agreement.
            game_time: Game-time snapshot at moment of formation.
            player_id: Optional player whose commitment this records.  Stored as
                ``subject_player_id`` so the memory can be retrieved via
                player-scoped queries (EXP-211).

        Returns:
            Memory ID string of the newly created node.
        """
        return await self._repo.create_memory(
            character_id=character_id,
            content=content,
            vividness=_COMMITMENT_VIVIDNESS,
            emotional_charge=_COMMITMENT_EMOTIONAL_CHARGE,
            game_time=game_time,
            subject_player_id=player_id,
            kind=MEMORY_KIND_COMMITMENT,
        )

    async def create_from_semantic_triggers(
        self,
        *,
        character_id: str,
        content: str,
        emotional_charge: int,
        game_time: TimePoint,
    ) -> str | None:
        """Create a memory if content contains a semantically significant keyword.

        Checks `content` (case-insensitively) against `_SEMANTIC_KEYWORDS`. If
        any keyword matches, a memory is formed at `_SEMANTIC_VIVIDNESS` (60)
        regardless of NPC arousal level. This is an OCP extension — it does not
        modify `create_from_arousal`.

        Args:
            character_id: ID of the NPC who formed the memory.
            content: Description of the moment to test for significance.
            emotional_charge: Emotional intensity (-100–100) passed through to
                the memory node unchanged.
            game_time: Game-time snapshot at moment of formation.

        Returns:
            Memory ID string if a keyword matched and a memory was created,
            else None.
        """
        lowered = content.lower()
        matched = any(keyword in lowered for keyword in _SEMANTIC_KEYWORDS)
        if not matched:
            return None
        return await self._repo.create_memory(
            character_id=character_id,
            content=content,
            vividness=_SEMANTIC_VIVIDNESS,
            emotional_charge=emotional_charge,
            game_time=game_time,
        )

    async def decay_vividness(self) -> int:
        """Reduce all memory vividness by the default daily decay amount.

        Returns:
            Number of Memory nodes updated.
        """
        return await self._repo.decay_all_vividness()

    async def decay_vividness_weighted(self) -> int:
        """Reduce memory vividness using a charge-weighted rate.

        High emotional_charge memories decay slower; trivial memories decay faster.
        Uses _DECAY_BASE_RATE and _DECAY_CHARGE_DIVISOR module constants.

        Returns:
            Number of Memory nodes whose vividness was reduced.
        """
        return await self._repo.decay_all_vividness_weighted(
            base_decay=_DECAY_BASE_RATE,
            charge_divisor=_DECAY_CHARGE_DIVISOR,
        )
