"""
dialogue package - Dialogue pipeline orchestration components.
Layer: engines
Purpose: Two-stage LLM dialogue pipeline — context assembly, prompt build, generation,
         response parsing, action resolution, bounded relation mutation, and graceful
         degradation (full → graph_only → canned).
Public surface: (list re-exports here)

Does NOT: expose HTTP route handlers directly.

Dependencies injected: None.
"""

from __future__ import annotations
