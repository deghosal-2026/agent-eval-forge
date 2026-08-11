"""LLM-backed test for the llamaindex adapter using local OMLX."""

import importlib.util
import os

import pytest

from evalforge.adapters.llamaindex import LlamaIndexAdapter
from evalforge.models.pack import Scenario

_LLAMAINDEX_AVAILABLE = importlib.util.find_spec("llama_index") is not None


def _omlx_is_healthy() -> bool:
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:8000/health")
        with urllib.request.urlopen(req, timeout=3):  # noqa: S310
            return True
    except Exception:
        return False


@pytest.mark.skipif(not _LLAMAINDEX_AVAILABLE, reason="llamaindex not installed")
@pytest.mark.skipif(not _omlx_is_healthy(), reason="OMLX server not reachable")
def test_llamaindex_llm_tool_call() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "omlx-test")
    os.environ.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")

    adapter = LlamaIndexAdapter()
    scenario = Scenario(
        id="sc-li-llm-1",
        title="LLM Test",
        input="What is the weather in London? Use the get_weather tool.",
        context={"mode": "tool_call"},
        allowed_tools=[{"name": "get_weather", "description": "Get weather"}],
    )
    config = {
        "module": "fixtures.llamaindex_real_agent",
        "function": "build_agent",
        "run_id": "llm-li-1",
        "timeout_seconds": 120,
    }
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.output.final is not None
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _LLAMAINDEX_AVAILABLE, reason="llamaindex not installed")
@pytest.mark.skipif(not _omlx_is_healthy(), reason="OMLX server not reachable")
def test_llamaindex_llm_no_tool() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "omlx-test")
    os.environ.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")

    adapter = LlamaIndexAdapter()
    scenario = Scenario(
        id="sc-li-llm-2",
        title="LLM Test No Tool",
        input="What is 2+2? Just give the number.",
        context={"mode": "no_tool"},
    )
    config = {
        "module": "fixtures.llamaindex_real_agent",
        "function": "build_agent",
        "run_id": "llm-li-2",
        "timeout_seconds": 120,
    }
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.output.final is not None
