"""
Package: graph.relations
Layer: graph
Purpose: Relation reads/writes, phase, and trust.
Public surface: submodules — relation_reader,relation_writer,relation_delta_writer,relation_phase_reader,relation_phase_writer,trust_queries.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
