from pathlib import Path

from evalforge.adapters.isolated import IsolatedAdapter
from evalforge.models.pack import Scenario

FIXTURES_DIR = str(Path(__file__).parent)


def _scenario(mode: str = "tool_call") -> Scenario:
    return Scenario(
        id="sc-1",
        title="Test",
        input="What is the weather in London?",
        context={"mode": mode},
    )


def _langgraph_config(mode: str = "tool_call") -> dict:
    return {
        "type": "isolated",
        "adapter_type": "langgraph",
        "module": "fixtures.langgraph_agent",
        "function": "build_agent",
        "run_id": "run-1",
        "timeout_seconds": 10,
        "env": {"PYTHONPATH": FIXTURES_DIR},
    }


def _pydantic_ai_config(mode: str = "tool_call") -> dict:
    return {
        "type": "isolated",
        "adapter_type": "pydantic-ai",
        "module": "fixtures.pydantic_ai_agent",
        "function": "build_agent",
        "run_id": "run-1",
        "timeout_seconds": 10,
        "env": {"PYTHONPATH": FIXTURES_DIR},
    }


def test_isolated_langgraph_tool_call() -> None:
    adapter = IsolatedAdapter()
    artifact = adapter.run(_scenario(), _langgraph_config())
    assert artifact.status == "completed"
    assert artifact.output.final == "The weather in London is 15\u00b0C."
    assert len(artifact.trajectory) == 3
    assert artifact.trajectory[0].type == "tool_call"
    assert artifact.trajectory[0].tool == "get_weather"
    assert artifact.trajectory[1].type == "tool_result"
    assert artifact.trajectory[2].type == "response"


def test_isolated_pydantic_ai_tool_call() -> None:
    adapter = IsolatedAdapter()
    artifact = adapter.run(_scenario(), _pydantic_ai_config())
    assert artifact.status == "completed"
    assert artifact.output.final == "The weather in London is 15\u00b0C."
    assert len(artifact.trajectory) == 3
    assert artifact.trajectory[0].type == "tool_call"
    assert artifact.trajectory[0].tool == "get_weather"
    assert artifact.trajectory[1].type == "tool_result"
    assert artifact.trajectory[2].type == "response"


def test_isolated_sandbox_mode() -> None:
    adapter = IsolatedAdapter()
    config = _langgraph_config()
    config["sandbox"] = True
    artifact = adapter.run(_scenario(mode="no_tool"), config)
    assert artifact.status == "error"


def test_isolated_timeout() -> None:
    adapter = IsolatedAdapter()
    config = {
        "type": "isolated",
        "adapter_type": "langgraph",
        "module": "fixtures.slow_agent",
        "function": "build_agent",
        "run_id": "run-1",
        "timeout_seconds": 1,
        "env": {"PYTHONPATH": FIXTURES_DIR},
    }
    artifact = adapter.run(_scenario(), config)
    assert artifact.status == "timeout"


def test_isolated_error_nonexistent_module() -> None:
    adapter = IsolatedAdapter()
    config = {
        "type": "isolated",
        "adapter_type": "langgraph",
        "module": "nonexistent.module",
        "function": "build_agent",
        "run_id": "run-1",
        "timeout_seconds": 10,
        "env": {"PYTHONPATH": FIXTURES_DIR},
    }
    artifact = adapter.run(_scenario(), config)
    assert artifact.status == "error"
    assert artifact.error and "nonexistent" in artifact.error.lower()


def test_isolated_error_bad_function() -> None:
    adapter = IsolatedAdapter()
    config = _langgraph_config()
    config["function"] = "nonexistent_function"
    artifact = adapter.run(_scenario(), config)
    assert artifact.status == "error"
    assert artifact.error and "nonexistent_function" in artifact.error


def test_isolated_missing_adapter_type() -> None:
    adapter = IsolatedAdapter()
    config = {
        "type": "isolated",
        "run_id": "run-1",
        "timeout_seconds": 10,
    }
    artifact = adapter.run(_scenario(), config)
    assert artifact.status == "error"
    assert "adapter_type" in (artifact.error or "").lower()


def test_isolated_missing_module() -> None:
    adapter = IsolatedAdapter()
    config = {
        "type": "isolated",
        "adapter_type": "langgraph",
        "run_id": "run-1",
        "timeout_seconds": 10,
    }
    artifact = adapter.run(_scenario(), config)
    assert artifact.status == "error"
    assert "module" in (artifact.error or "").lower()
