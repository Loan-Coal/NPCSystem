"""
engines package - Runtime engine implementations and interfaces.
Layer: engines
Purpose: Domain engine implementations (request- and tick-driven) plus their shared
         interfaces — the orchestration layer between api/services and the graph.
Public surface: (list re-exports here)

Does NOT: expose API routes directly.

Dependencies injected: None.
"""

from __future__ import annotations
