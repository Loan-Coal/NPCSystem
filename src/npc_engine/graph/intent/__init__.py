"""
Package: graph.intent
Layer: graph
Purpose: Intent queue and interaction reads/writes.
Public surface: submodules — intent_queries,intent_queue_reader,intent_queue_writer,interaction_queries.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
