"""
Package: graph.memory
Layer: graph
Purpose: Memory reads, writes, and proactive recall.
Public surface: submodules — memory_queries,memory_service,proactive_memory_reader.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
