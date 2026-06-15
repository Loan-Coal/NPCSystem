"""
Module: config_logging_validators
Layer: config
Purpose: Pure validators that gate verbose/sensitive logging settings to dev only (L1-12).
Does NOT: read from environment, instantiate Settings, or perform I/O.
Dependencies: None.
Dependencies injected: None.
Used by: config.Settings (production-logging model validator), test_config_validators.
"""

from __future__ import annotations


def check_log_level(value: str, env: str) -> str:
    """Reject DEBUG log verbosity outside dev (L1-12).

    DEBUG is allowed in dev for local debugging, but in staging/prod it risks
    verbose internal detail in logs; callers must set INFO or higher.

    Args:
        value: Raw LOG_LEVEL value from the environment.
        env: Current ENV value ("dev", "staging", or "prod").

    Returns:
        The log level string unchanged when valid.

    Raises:
        ValueError: when value is "DEBUG" and env is not "dev".
    """
    if value == "DEBUG" and env != "dev":
        raise ValueError(
            "LOG_LEVEL must not be DEBUG in staging/prod. "
            "Set LOG_LEVEL=INFO or higher via the LOG_LEVEL environment variable."
        )
    return value


def check_log_llm_prompts(enabled: bool, env: str) -> bool:
    """Reject LLM prompt/response logging outside dev (L1-12).

    Prompt logging may capture player PII and internal prompt content; it is a
    dev-only debugging aid and must be off in staging/prod.

    Args:
        enabled: Raw LOG_LLM_PROMPTS value from the environment.
        env: Current ENV value ("dev", "staging", or "prod").

    Returns:
        The flag unchanged when valid.

    Raises:
        ValueError: when enabled is True and env is not "dev".
    """
    if enabled and env != "dev":
        raise ValueError(
            "LOG_LLM_PROMPTS must be false in staging/prod; prompt/response "
            "logging is dev-only. Set LOG_LLM_PROMPTS=false."
        )
    return enabled
