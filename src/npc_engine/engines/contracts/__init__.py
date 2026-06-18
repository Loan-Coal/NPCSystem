"""
contracts package - Engine contract schema and loading utilities.
Layer: engines
Purpose: Engine contract schema and loader; declares per-engine metadata (e.g. uses_llm)
         validated fail-fast at startup.
Public surface: (list re-exports here)

Does NOT: execute engine runtime logic.

Dependencies injected: None.
"""

from __future__ import annotations
