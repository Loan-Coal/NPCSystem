"""
Package: services
Layer: services
Purpose: Shared domain services (moderation, rating resolution) consumed by engines and API.
Does NOT: define HTTP routes, graph queries, or LLM calls.
Dependencies injected: None at the package level; each service takes deps via __init__.
Public surface: ContentRatingResolver, InputModerationService, OutputModerationService.
"""

from __future__ import annotations
