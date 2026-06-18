"""
Package: economy
Layer: engines
Purpose: Economy engine — deterministic item pricing and trade offer evaluation.
Does NOT: execute graph queries or call LLMs directly.
Dependencies injected: None.
Public surface: PricingEngine, PricingRules, TradeEngine, TradeResult
"""

from __future__ import annotations

from npc_engine.engines.economy.pricing_engine import PricingEngine
from npc_engine.engines.economy.pricing_rules_loader import PricingRules, load_pricing_rules
from npc_engine.engines.economy.trade_engine import TradeEngine
from npc_engine.engines.economy.trade_models import TradeResult

__all__ = ["PricingEngine", "PricingRules", "TradeEngine", "TradeResult", "load_pricing_rules"]
