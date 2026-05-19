"""
Package: chapter
Layer: engines
Purpose: Chapter detection and LLM-based narrative labeling engine.
Does NOT: expose HTTP routes or manage tick scheduling.
Dependencies: engines.chapter.chapter_engine
Dependencies injected: None (engines are constructed in dependency_singletons).
Public surface: ChapterEngine
"""

from npc_engine.engines.chapter.chapter_engine import ChapterEngine

__all__ = ["ChapterEngine"]
