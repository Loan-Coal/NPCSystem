"""
Package: setup
Layer: config
Purpose: First-run bootstrap utilities — VRAM detection, Ollama management, model
         tier selection, and the end-to-end local-inference setup flow (SHIP-03).
Public surface: run_first_run_flow, detect_vram_mb, select_model_for_vram,
                OllamaManager
Does NOT: import any engine, graph, or API layer.
Dependencies injected: None (all submodules inject their own deps).
"""
from __future__ import annotations
