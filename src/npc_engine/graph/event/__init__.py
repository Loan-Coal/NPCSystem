"""
Package: graph.event
Layer: graph
Purpose: Event emission, feed, and triggers.
Public surface: submodules — event_queries,event_writer,event_emission_service,event_feed_queries,event_trigger_queries.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
