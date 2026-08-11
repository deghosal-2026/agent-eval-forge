"""LLM-backed test for the autogen adapter using local OMLX."""

import importlib.util
import os

import pytest

from evalforge.adapters.autogen import AutoGenAdapter
from evalforge.models.pack import Scenario

_AUTOGEN_AVAILABLE = importlib.util.find_spec("autogen_agentchat") is not None


def _omlx_is_healthy() -> bool:
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:8000/health")
        with urllib.request.urlopen(req, timeout=3):  # noqa: S310
            return True
    except Exception:
        return False


@pytest.mark.skipif(not _AUTOGEN_AVAILABLE, reason="autogen not installed")
@pytest.mark.skipif(not _omlx_is_healthy(), reason="OMLX server not reachable")
def test_autogen_llm_tool_call() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "omlx-test")
    os.environ.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")

    adapter = AutoGenAdapter()
    scenario = Scenario(
        id="sc-ag-llm-1",
        title="LLM Test",
        input="What is the weather in London? Use the get_weather tool.",
        context={"mode": "tool_call"},
        allowed_tools=[{"name": "get_weather", "description": "Get weather"}],
    )
    config = {
        "module": "fixtures.autogen_real_agent",
        "function": "build_agent",
        "run_id": "llm-ag-1",
        "timeout_seconds": 120,
    }
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.output.final is not None
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _AUTOGEN_AVAILABLE, reason="autogen not installed")
@pytest.mark.skipif(not _omlx_is_healthy(), reason="OMLX server not reachable")
def test_autogen_llm_no_tool() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "omlx-test")
    os.environ.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")

    adapter = AutoGenAdapter()
    scenario = Scenario(
        id="sc-ag-llm-2",
        title="LLM Test No Tool",
        input="What is 2+2? Just give the number.",
        context={"mode": "no_tool"},
    )
    config = {
        "module": "fixtures.autogen_real_agent",
        "function": "build_agent",
        "run_id": "llm-ag-2",
        "timeout_seconds": 120,
    }
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.output.final is not None
