"""
trading_engine.py - Re-exports item transfer validator from graph.transfer_validators.

Does NOT: execute graph writes.

Dependencies injected: None.
"""

# Validator and command class have moved to graph/transfer_validators.py (V1 fix).
# This module re-exports them so existing callers outside graph/ are unaffected
# until service #13 cleans up engines/economy/.
from graph.transfer_validators import ItemTransferCommand, build_item_transfer_command

__all__ = ["ItemTransferCommand", "build_item_transfer_command"]
