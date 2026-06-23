"""
Package: graph.idempotency
Layer: graph
Purpose: Idempotency models, queries, and writes.
Public surface: submodules — idempotency_models,idempotency_queries,idempotency_writer.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
