"""
Package: graph.gossip
Layer: graph
Purpose: Gossip and rumor spread reads/writes.
Public surface: submodules — gossip_queries,gossip_write_queries,gossip_batch_queries,gossip_spread_service,rumor_queries,rumor_service,rumor_trace_service.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
