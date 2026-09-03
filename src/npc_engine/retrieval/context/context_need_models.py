"""
Module: context_need_models
Layer: retrieval
Purpose: Typed snapshot model and urgency threshold for the NPC need surfaced into dialogue context.
Does NOT: query the graph, score, or assemble context items — model definitions only.
Dependencies: pydantic.
Dependencies injected: none.
Used by: retrieval.context.context_graph_readers, retrieval.context.context_builder
"""

from __future__ import annotations

from pydantic import BaseModel


# Level below which a need is considered "unmet" and surfaced to dialogue context.
# Needs are modelled on a 0-100 scale; lower = more urgent.
NEED_UNMET_LEVEL_THRESHOLD: int = 50


class NeedSnapshot(BaseModel):
    """Typed snapshot of a single NPC need node — no raw dict crosses module boundary.

    Attributes:
        need_id: Unique node ID in the graph.
        kind:    Semantic kind (e.g. "hunger", "social", "rest").
        level:   Current level on a 0-100 scale.  Lower = more urgent.
        character_id: Owning NPC node ID.
    """

    need_id: str
    kind: str
    level: int
    character_id: str
