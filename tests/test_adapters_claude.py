from evalforge.adapters.claude import ClaudeAgentSDKAdapter
from evalforge.models.pack import Scenario


def _scenario(mode: str = "tool_call") -> Scenario:
    return Scenario(
        id="sc-1",
        title="Test",
        input="What is the weather in London?",
        context={"mode": mode},
        allowed_tools=[{"name": "get_weather", "description": "Get weather"}],
    )


def _config(mode: str = "tool_call") -> dict:
    return {
        "module": "fixtures.claude_agent",
        "function": "build_agent",
        "run_id": "run-1",
        "timeout_seconds": 10,
    }


def test_claude_tool_call_trajectory() -> None:
    adapter = ClaudeAgentSDKAdapter()
    artifact = adapter.run(_scenario(), _config())
    assert artifact.status == "completed"
    assert artifact.output.final == "The weather in London is 15°C."
    assert len(artifact.trajectory) == 3
    assert artifact.trajectory[0].type == "tool_call"
    assert artifact.trajectory[0].tool == "get_weather"
    assert artifact.trajectory[0].args == {"city": "London"}
    assert artifact.trajectory[1].type == "tool_result"
    assert artifact.trajectory[1].tool == "get_weather"
    assert artifact.trajectory[2].type == "response"
    assert artifact.trajectory[2].content == "The weather in London is 15°C."


def test_claude_no_tools() -> None:
    adapter = ClaudeAgentSDKAdapter()
    artifact = adapter.run(_scenario(mode="no_tool"), _config(mode="no_tool"))
    assert artifact.status == "completed"
    assert artifact.output.final == "I don't have enough information to answer."
    assert len(artifact.trajectory) == 1
    assert artifact.trajectory[0].type == "response"


def test_claude_structured_output() -> None:
    adapter = ClaudeAgentSDKAdapter()
    artifact = adapter.run(_scenario(mode="structured"), _config(mode="structured"))
    assert artifact.status == "completed"
    assert artifact.output.structured == {"temperature": 15, "condition": "sunny"}


def test_claude_missing_module() -> None:
    config = _config()
    config["module"] = "nonexistent.module"
    adapter = ClaudeAgentSDKAdapter()
    artifact = adapter.run(_scenario(), config)
    assert artifact.status == "error"
    assert "claude" in (artifact.error or "").lower()
