"""
Package: faction_politics
Layer: engines
Purpose: Deterministic engine that drifts faction standings based on world events and time decay.
Does NOT: call LLMs or expose HTTP routes directly.
Dependencies injected: None at package level.
Public surface: FactionPoliticsEngine, load_rules, FactionPoliticsRules
"""
