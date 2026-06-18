"""
gossip package - NPC-to-NPC gossip propagation modules.
Layer: engines
Purpose: Deterministic NPC-to-NPC rumor propagation with personality/faction-weighted pair
         selection and distortion (omission, exaggeration, role-swap, timeline-shift).
Public surface: (list re-exports here)

Does NOT: expose API routes.

Dependencies injected: None.
"""

from __future__ import annotations
