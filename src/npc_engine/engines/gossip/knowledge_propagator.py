"""
Module: knowledge_propagator
Layer: engines/gossip
Purpose: Re-exports gossip secret-propagation constants (formerly also held dead
         session-based propagate/propagate_secret helpers; those moved to GossipGraphPort
         in the Wave-4 gossip cluster migration, DEC-122 / SEV-24).
Does NOT: open sessions, write graph nodes, or call LLMs.
Dependencies: engines/gossip/gossip_config (constants).
Dependencies injected: None.
Used by: engines/gossip/gossip_handler (SECRET_DISTORTION_CHANCE).
"""

from __future__ import annotations

from npc_engine.engines.gossip.gossip_config import (
    SECRET_BASE_PROBABILITY,
    SECRET_DISTORTION_CHANCE,
)

__all__ = ["SECRET_BASE_PROBABILITY", "SECRET_DISTORTION_CHANCE"]
