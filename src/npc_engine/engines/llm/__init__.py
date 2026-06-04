"""
Package: engines.llm
Layer: engines
Purpose: LLM backend adapters and the backend registry/factory.
Public surface: factory (register_backend, registered_backends,
    create_llm_client_for_engine).

Importing this package imports the factory, which registers the built-in
backends (mock, ollama). New backends should register themselves at import time
and be imported here so the registry is populated on package import (L7-07).
Does NOT: orchestrate dialogue pipeline logic.
Dependencies injected: None.
"""

from __future__ import annotations

# Import for the registration side-effect so registered_backends() is populated
# whenever the package is imported (not only when factory is imported elsewhere).
from npc_engine.engines.llm import factory as factory  # noqa: F401
