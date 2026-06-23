"""
Package: workers
Layer: demo_game
Purpose: Thread worker functions that call the engine API for player actions.
Public surface: dialogue_worker, fetch_sidebar_worker, generate_quest_worker,
  travel_worker, bribe_worker, consolidate_memory_worker, spread_rumor_worker,
  correct_rumor_worker, inspect_worker.
Does NOT: import from src/.
"""

from .action_workers import (
    dialogue_worker,
    fetch_sidebar_worker,
    generate_quest_worker,
    travel_worker,
    bribe_worker,
    consolidate_memory_worker,
    spread_rumor_worker,
    correct_rumor_worker,
    inspect_worker,
)
