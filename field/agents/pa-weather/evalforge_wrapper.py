"""EvalForge field-test wrapper for weather-agent-pydanticAI repo.

The repo's own module imports a pydantic-ai API no longer present in
pydantic-ai 2.x; this shim exposes a fresh tool-calling agent wired to the
field OMLX/cloud endpoint so it can be scored by the EvalForge harness.
"""

from __future__ import annotations

import os

from pydantic_ai import Agent
from pydantic_ai.tools import Tool


def _make_model():
    model = os.environ.get("EVALFORGE_FIELD_MODEL", "Qwen3.5-4B-4bit")
    endpoint = os.environ.get("EVALFORGE_FIELD_ENDPOINT", "http://127.0.0.1:8000/v1")
    api_key = os.environ.get("OPENAI_API_KEY") or "omlx-test"

    try:
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIModel(model, provider=OpenAIProvider(base_url=endpoint, api_key=api_key))
    except ImportError:
        pass
    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIChatModel(model, provider=OpenAIProvider(base_url=endpoint, api_key=api_key))
    except ImportError:
        pass
    try:
        from pydantic_ai.models.openai import OpenAIModel
        return OpenAIModel(model, base_url=endpoint, api_key=api_key)
    except Exception:
        raise


def _get_current_date() -> str:
    import datetime
    return datetime.date.today().isoformat()


def _add(a: int, b: int) -> int:
    return a + b


def build_agent() -> Agent:
    return Agent(_make_model(), tools=[Tool(_get_current_date), Tool(_add)])