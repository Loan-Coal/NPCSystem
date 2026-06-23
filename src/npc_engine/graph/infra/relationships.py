"""
Module: relationships
Layer: graph
Purpose: Relationship type constants for Cypher query composition.
Does NOT: contain query logic; purely declarative string constants.
Dependencies injected: none
Dependencies: none
Used by: graph/* query modules
"""
from __future__ import annotations

KNOWS_ABOUT: str = "KNOWS_ABOUT"
KNOWS_SECRET: str = "KNOWS_SECRET"
RELATES_TO: str = "RELATES_TO"
LOCATED_AT: str = "LOCATED_AT"
MEMBER_OF: str = "MEMBER_OF"
STANDS_WITH: str = "STANDS_WITH"
HAS_ITEM: str = "HAS_ITEM"
PARTICIPATES_IN: str = "PARTICIPATES_IN"
