"""
Package: graph.world_state
Layer: graph
Purpose: World-state node reads and writes.
Public surface: submodules — world_state_reader,world_state_writer.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
