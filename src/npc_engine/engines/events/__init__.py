"""
events package - Autonomous world event generation modules.
Layer: engines
Purpose: Autonomous world-event generation — samples weighted event templates, scopes them
         to locations, and seeds NPC awareness via KNOWS_ABOUT edges.
Public surface: (list re-exports here)

Does NOT: run scheduler loops directly.

Dependencies injected: None.
"""

from __future__ import annotations
