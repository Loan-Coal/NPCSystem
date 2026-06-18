"""
Package: setup
Layer: config
Purpose: First-run bootstrap utilities (SHIP-03) and full-stack process launcher
         (SHIP-04) — VRAM detection, Ollama management, Neo4j management, model-tier
         selection, the first-run flow, and the StackLauncher orchestrator.
Public surface: detect_vram_mb, select_model_for_vram, OllamaManager, FirstRunFlow,
                FirstRunResult, FirstRunStatus, Neo4jManager, StackLauncher
Does NOT: import any engine, services, graph, or API layer module.
Dependencies injected: None (all submodules inject their own deps via constructors).
"""
from __future__ import annotations
