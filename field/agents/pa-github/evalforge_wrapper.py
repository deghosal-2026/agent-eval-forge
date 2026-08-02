"""EvalForge field-test wrapper for library/notebook repos.

Exposes a simple tool-calling PydanticAI agent wired to the field
OMLX/cloud endpoint so it can be scored by the EvalForge field harness.
Tolerant of pydantic-ai 1.x and 2.x model/provider class names.
"""

from __future__ import annotations

import os

from pydantic_ai import Agent
from pydantic_ai.tools import Tool


def _make_model():
    model = os.environ.get("EVALFORGE_FIELD_MODEL", "Qwen3.5-4B-4bit")
    endpoint = os.environ.get("EVALFORGE_FIELD_ENDPOINT", "http://127.0.0.1:8000/v1")
    api_key = os.environ.get("OPENAI_API_KEY") or "omlx-test"

    # pydantic-ai >= 0.x, <2: OpenAIModel(model, provider=OpenAIProvider(...))
    try:
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIModel(model, provider=OpenAIProvider(base_url=endpoint, api_key=api_key))
    except ImportError:
        pass
    # pydantic-ai 2.x: OpenAIChatModel(model, provider=OpenAIProvider(...))
    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIChatModel(model, provider=OpenAIProvider(base_url=endpoint, api_key=api_key))
    except ImportError:
        pass
    # Fallback: legacy positional base_url/api_key
    try:
        from pydantic_ai.models.openai import OpenAIModel
        return OpenAIModel(model, base_url=endpoint, api_key=api_key)
    except Exception:
        raise


def _get_current_date() -> str:
    """Return today's date as YYYY-MM-DD."""
    import datetime
    return datetime.date.today().isoformat()


def _add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b


def build_agent() -> Agent:
    return Agent(_make_model(), tools=[Tool(_get_current_date), Tool(_add)])