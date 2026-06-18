"""
Package: setup
Layer: config
Purpose: First-run bootstrap utilities (SHIP-03/04/05a) — VRAM detection, Ollama
         management, Neo4j management, model-tier selection, the first-run flow,
         the StackLauncher orchestrator, and the wizard config / path validators.
Public surface: detect_vram_mb, select_model_for_vram, OllamaManager, FirstRunFlow,
                FirstRunResult, FirstRunStatus, Neo4jManager, StackLauncher,
                LLMPath, WizardConfig, load_wizard_config, save_wizard_config,
                ValidationStatus, ValidationResult, validate_path_a, validate_path_b
Does NOT: import any engine, services, graph, or API layer module.
Dependencies injected: None (all submodules inject their own deps via constructors).
"""
from __future__ import annotations
