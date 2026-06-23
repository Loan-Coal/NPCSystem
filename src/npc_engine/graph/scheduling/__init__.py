"""
Package: graph.scheduling
Layer: graph
Purpose: Schedules, routines, and tick leases.
Public surface: submodules — schedule_queries,schedule_service,schedule_writer,routine_queries,tick_lease_queries,tick_scheduler_queries.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
