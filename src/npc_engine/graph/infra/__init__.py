"""
Package: graph.infra
Layer: graph
Purpose: Cross-cutting graph plumbing: db, labels, relationship types, transactions, bootstrap, metrics.
Public surface: submodules — db,labels,relationships,json_fields,transaction_coordinator,schema_bootstrap,write_metrics,delta_log_writer,transfer_validators,replay_helpers,session_persistence,embedding_sync_queries.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
