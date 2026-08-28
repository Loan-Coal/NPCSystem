"""
Module: npc_profile_data_models
Layer: config
Purpose: The named container for one NPC's per-turn profile reads, replacing a raw 9-tuple
         that was unpacked positionally and cached opaquely.
Does NOT: perform the reads, cache anything, or validate graph payload contents.
Dependencies injected: none -- values are supplied by the caller.
Used by: retrieval.context.context_builder and the partial dialogue-context cache.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["NpcProfileData"]


class NpcProfileData(BaseModel):
    """One NPC's per-turn profile reads, in one named object.

    This was ``tuple[Any, ...]`` -- nine graph reads returned positionally, unpacked
    positionally 300 lines away, and stored in a process-wide cache as an anonymous tuple.
    Adding a read meant editing both ends in lockstep, and getting the order wrong was a
    silent mis-assignment, not an error. It also violated the project's own rule that no
    raw container crosses a module boundary.

    The fields are graph payloads that the readers have already shaped; they are held as
    ``Any`` deliberately rather than re-validated here, because re-validating them would
    make this module the second place a node's shape is described.

    Attributes:
        location_context: The NPC's current location subgraph, or an empty mapping.
        events: Events the NPC knows about, newest first, capped by ``profile.events_limit``.
        reputation_items: Player reputation lines relevant to the NPC's factions.
        memories: The NPC's own memories, ordered by vividness.
        owned_items: Items the NPC holds.
        group_memberships: Groups the NPC belongs to.
        believed_rumors: Rumours the NPC believes, ordered by confidence.
        traits: The NPC's character traits, ordered by intensity.
        active_pledges: Political pledges the NPC is currently bound by.
    """

    location_context: Any = None
    events: list[Any] = Field(default_factory=list)
    reputation_items: list[Any] = Field(default_factory=list)
    memories: list[Any] = Field(default_factory=list)
    owned_items: list[Any] = Field(default_factory=list)
    group_memberships: list[Any] = Field(default_factory=list)
    believed_rumors: list[Any] = Field(default_factory=list)
    traits: list[Any] = Field(default_factory=list)
    active_pledges: list[Any] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True, extra="forbid")
