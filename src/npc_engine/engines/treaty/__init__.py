"""
Package: treaty
Layer: engines
Purpose: Engine for managing treaty lifecycle — expiry and mechanical/LLM condition checking.
Does NOT: modify faction standings directly or implement gossip/event logic.
Dependencies injected: AsyncSession (via run_tick).
Public surface: TreatyEngine
"""
