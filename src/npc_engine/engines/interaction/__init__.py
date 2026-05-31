"""
Package: interaction
Layer: engines
Purpose: Interaction proposal dispatch — routes action proposals from dialogue into
         trade and quest handlers without coupling the dialogue engine to either.
Does NOT: implement quest business logic (Phase 3 covers trade; Phase 4 covers quest).
Dependencies injected: None.
Public surface: InteractionProposal, InteractionState, NegotiationSession,
    NegotiationStore, dispatch_interaction
"""

from npc_engine.engines.interaction.models import InteractionProposal, InteractionState
from npc_engine.engines.interaction.dispatch import dispatch_interaction
from npc_engine.engines.interaction.negotiation_store import NegotiationSession, NegotiationStore

__all__ = [
    "InteractionProposal",
    "InteractionState",
    "NegotiationSession",
    "NegotiationStore",
    "dispatch_interaction",
]
