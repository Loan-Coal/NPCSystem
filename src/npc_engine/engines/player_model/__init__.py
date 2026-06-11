"""
Package: player_model
Layer: engines
Purpose: Theory-of-mind engine — derives and exposes an NPC's model of the player
         (perceived_trust, perceived_intent) from relation scalars.
Does NOT: perform I/O or call the graph (the engine is pure; persistence lives in graph/player_model_writer).
Dependencies injected: None (pure package; the engine is stateless).
Public surface: PlayerModelEngine, PlayerModelInput, PlayerModelUpdate
"""

from npc_engine.engines.player_model.player_model_engine import (
    PlayerModelEngine,
    PlayerModelInput,
    PlayerModelUpdate,
)

__all__ = ["PlayerModelEngine", "PlayerModelInput", "PlayerModelUpdate"]
