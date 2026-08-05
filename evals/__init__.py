"""
Package: evals
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Evaluation harness for the NPC Engine. Contains case fixtures, runners,
         matchers, and the single sanctioned adapter for importing from npc_engine.
Public surface: engine_adapter (the only module permitted to import from npc_engine).
"""
