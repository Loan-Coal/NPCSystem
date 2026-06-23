"""
Package: graph.economy
Layer: graph
Purpose: Items, currency, pricing, and debts.
Public surface: submodules — item_queries,item_service,item_writer,currency_queries,currency_writer,pricing_queries,owes_queries,owes_service.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
