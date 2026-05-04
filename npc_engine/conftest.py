"""
conftest.py - Pytest root configuration for the NPC Engine test suite.

Does NOT: define fixtures or test helpers.

Dependencies injected: None.
"""

import os

# Provide required env vars so test collection can import `main` without a .env file.
# Uses setdefault so a real value in the shell always takes precedence.
os.environ.setdefault("API_KEY_SECRET", "test-api-key-secret")
