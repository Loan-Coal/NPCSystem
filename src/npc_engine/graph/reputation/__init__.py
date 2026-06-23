"""
Package: graph.reputation
Layer: graph
Purpose: Reputation reads, writes, and seeding.
Public surface: submodules — reputation_queries,reputation_writer,reputation_service,reputation_event_seeder,reputation_nudge.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
