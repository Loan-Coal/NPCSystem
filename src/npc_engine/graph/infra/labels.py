"""
Module: labels
Layer: graph
Purpose: Node label constants for Cypher query composition.
Does NOT: contain query logic; purely declarative string constants.
Dependencies injected: none
Dependencies: none
Used by: graph/* query modules
"""
from __future__ import annotations

CHARACTER: str = "Character"
EVENT: str = "Event"
SECRET: str = "Secret"
LOCATION: str = "Location"
FACTION: str = "Faction"
QUEST: str = "Quest"
ITEM: str = "Item"
WORLD: str = "WorldState"
