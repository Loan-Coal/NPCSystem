"""
Package: graph.character
Layer: graph
Purpose: Character, trait, skill state, and player-model writes.
Public surface: submodules — character_reader,character_writer,trait_queries,trait_service,skill_queries,skill_service,player_model_writer.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
