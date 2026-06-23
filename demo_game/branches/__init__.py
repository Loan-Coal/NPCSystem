"""
Package: branches
Layer: demo_game
Purpose: Branching narrative nodes, effects, and session state for the demo.
Public surface: BranchOption, BranchNode, build_garrick_branch (from branch_node);
  BranchEffect, RepDeltaEffect, SetBeliefEffect, WorldStateEffect, OfferQuestEffect,
  GotoBeatEffect (from branch_effects); ChoiceRecord, BranchState,
  save_branch_state, load_branch_state (from branch_state).
Does NOT: import from src/.
"""

from .branch_node import BranchOption, BranchNode, build_garrick_branch
from .branch_effects import (
    BranchEffect,
    RepDeltaEffect,
    SetBeliefEffect,
    WorldStateEffect,
    OfferQuestEffect,
    GotoBeatEffect,
)
from .branch_state import ChoiceRecord, BranchState, save_branch_state, load_branch_state
