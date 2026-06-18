"""
currency.__init__.py - Currency engine namespace for currency and trading safety flows.
Layer: engines
Purpose: Bounded, auditable currency-transfer safety flows backing trades and player actions.
Public surface: (list re-exports here)

Does NOT: execute transfer writes directly.

Dependencies injected: None.
"""

from __future__ import annotations
