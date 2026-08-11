"""LLM-backed integration test for the smolagents adapter using local OMLX.

Requires the local OMLX server running on http://127.0.0.1:8000/v1 with a
Qwen3.5-4B-4bit model available. Uses ``fixtures.smolagents_real_agent`` which
builds a real smolagents ``CodeAgent`` with one tool.
"""

import importlib.util
import os

import pytest

from evalforge.adapters.smolagents import SmolagentsAdapter
from evalforge.models.pack import Scenario

_SMOLAGENTS_AVAILABLE = importlib.util.find_spec("smolagents") is not None

OMLX_HEALTH_URL = "http://127.0.0.1:8000/health"


def _omlx_is_healthy() -> bool:
    try:
        import urllib.request
        req = urllib.request.Request(OMLX_HEALTH_URL)
        with urllib.request.urlopen(req, timeout=3):  # noqa: S310
            return True
    except Exception:
        return False


def _scenario(mode: str = "tool_call") -> Scenario:
    return Scenario(
        id="sc-llm-1",
        title="LLM Test",
        input="What is the weather in London? Use the get_weather tool.",
        context={"mode": mode},
        allowed_tools=[{"name": "get_weather", "description": "Get weather"}],
    )


def _config() -> dict:
    return {
        "module": "fixtures.smolagents_real_agent",
        "function": "build_agent",
        "run_id": "llm-run-1",
        "timeout_seconds": 60,
    }


@pytest.mark.skipif(not _SMOLAGENTS_AVAILABLE, reason="smolagents not installed")
@pytest.mark.skipif(not _omlx_is_healthy(), reason="OMLX server not reachable")
def test_smolagents_llm_tool_call() -> None:
    """Real LLM-backed test: smolagents + OMLX with a weather tool."""
    os.environ.setdefault("OPENAI_API_KEY", "omlx-test")
    os.environ.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")

    adapter = SmolagentsAdapter()
    artifact = adapter.run(_scenario(), _config())
    assert artifact.status == "completed"
    assert artifact.output.final is not None
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _SMOLAGENTS_AVAILABLE, reason="smolagents not installed")
@pytest.mark.skipif(not _omlx_is_healthy(), reason="OMLX server not reachable")
def test_smolagents_llm_no_tool() -> None:
    """Real LLM-backed test: smolagents + OMLX without tools."""
    os.environ.setdefault("OPENAI_API_KEY", "omlx-test")
    os.environ.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")

    adapter = SmolagentsAdapter()
    scenario = Scenario(
        id="sc-llm-2",
        title="LLM Test No Tool",
        input="What is 2+2? Just give the answer.",
        context={"mode": "no_tool"},
    )
    config = _config()
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.output.final is not None
