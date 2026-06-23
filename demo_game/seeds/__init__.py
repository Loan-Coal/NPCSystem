"""
Package: seeds
Layer: demo_game
Purpose: Demo world seeder — builds all nodes and edges for the 5-NPC demo world.
Public surface: Import directly from submodules to avoid circular imports:
  demo_game.seeds.seed (seed_all, WorldStatePayload)
  demo_game.seeds.seed_npc_data (NPC_ID_*, FACTION_ID_*, LOC_ID_*, H2_* constants)
Does NOT: import from src/.
"""
