"""EvalForge field-test wrapper for the eval-graph repo.

The repo's judge_graph is a code-evaluation StateGraph (not a chat agent),
so this shim exposes a standard ReAct tool-calling agent wired to the field
OMLX/cloud endpoint for scoring by the EvalForge field harness.
"""

from __future__ import annotations

import os

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent


def build_agent():
    model = os.environ.get("EVALFORGE_FIELD_MODEL", "Qwen3.5-4B-4bit")
    endpoint = os.environ.get("EVALFORGE_FIELD_ENDPOINT", "http://127.0.0.1:8000/v1")
    api_key = os.environ.get("OPENAI_API_KEY") or "omlx-test"
    llm = ChatOpenAI(model=model, base_url=endpoint, api_key=api_key)

    @tool
    def get_current_date() -> str:
        """Return today's date as YYYY-MM-DD."""
        import datetime
        return datetime.date.today().isoformat()

    @tool
    def add(a: int, b: int) -> int:
        """Add two integers and return the sum."""
        return a + b

    return create_react_agent(llm, [get_current_date, add])
