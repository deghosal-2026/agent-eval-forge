from evalforge.adapters.pydantic_ai import PydanticAIAdapter
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
        "module": "fixtures.pydantic_ai_agent",
        "function": "build_agent",
        "run_id": "run-1",
        "timeout_seconds": 10,
    }


def test_pydantic_ai_tool_call_trajectory() -> None:
    adapter = PydanticAIAdapter()
    artifact = adapter.run(_scenario(), _config())
    assert artifact.status == "completed"
    assert artifact.output.final == "The weather in London is 15°C."
    assert len(artifact.trajectory) == 3
    assert artifact.trajectory[0].type == "tool_call"
    assert artifact.trajectory[0].tool == "get_weather"
    assert artifact.trajectory[1].type == "tool_result"
    assert artifact.trajectory[1].tool == "get_weather"
    assert artifact.trajectory[2].type == "response"


def test_pydantic_ai_no_tools() -> None:
    adapter = PydanticAIAdapter()
    artifact = adapter.run(_scenario(mode="no_tool"), _config(mode="no_tool"))
    assert artifact.status == "completed"
    assert artifact.output.final == "I have no tools available."
    assert len(artifact.trajectory) == 1
    assert artifact.trajectory[0].type == "response"


def test_pydantic_ai_structured_output() -> None:
    adapter = PydanticAIAdapter()
    artifact = adapter.run(_scenario(mode="structured"), _config(mode="structured"))
    assert artifact.status == "completed"
    assert artifact.output.structured == {"temperature": 15, "condition": "sunny"}


def test_pydantic_ai_missing_module() -> None:
    config = _config()
    config["module"] = "nonexistent.module"
    adapter = PydanticAIAdapter()
    artifact = adapter.run(_scenario(), config)
    assert artifact.status == "error"
    assert "pydantic" in (artifact.error or "").lower()
