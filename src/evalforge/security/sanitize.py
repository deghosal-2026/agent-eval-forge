"""API key and secret sanitization utilities.

Extends ``_sanitize_agent`` in ``adapters/base.py`` with regex-based
redaction so secrets are removed even from nested dicts and strings.
"""

from __future__ import annotations

import re
from typing import Any

# Keys whose values should always be redacted
SANITIZE_KEYS = {"api_key", "token", "secret", "password", "credential", "auth_token"}

# Patterns that look like API keys or tokens in string values
SANITIZE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),   # OpenAI-style keys
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),  # Anthropic-style keys
    re.compile(r"ghp_[A-Za-z0-9_-]{36,}"),   # GitHub PATs
    re.compile(r"gho_[A-Za-z0-9_-]{36,}"),   # GitHub OAuth
]


def _redact_string(value: str) -> str:
    """Redact any API-key-like patterns in a string."""
    for pattern in SANITIZE_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def sanitize_config(config: dict[str, Any], _depth: int = 0) -> dict[str, Any]:
    """Deep-sanitize a config dict, handling nesting."""
    if _depth > 10:
        return {"[REDACTED]": "[max depth]"}
    result: dict[str, Any] = {}
    for key, value in config.items():
        if key in SANITIZE_KEYS:
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = sanitize_config(value, _depth + 1)
        elif isinstance(value, str):
            result[key] = _redact_string(value)
        else:
            result[key] = value
    return result
