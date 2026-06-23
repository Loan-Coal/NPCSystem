"""
Package: graph.needs_goals
Layer: graph
Purpose: Needs and goals reads/writes.
Public surface: submodules — need_queries,need_writer,goal_queries,goal_service,goal_targets_writer.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
