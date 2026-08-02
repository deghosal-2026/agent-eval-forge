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
        "module": "fixtures.langgraph_agent",
        "function": "build_agent",
        "run_id": "run-1",
        "timeout_seconds": 10,
    }


def test_langgraph_tool_call_trajectory() -> None:
    from evalforge.adapters.langgraph import LangGraphAdapter

    adapter = LangGraphAdapter()
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


def test_langgraph_multi_tool_trajectory() -> None:
    from evalforge.adapters.langgraph import LangGraphAdapter

    adapter = LangGraphAdapter()
    artifact = adapter.run(_scenario(mode="multi_tool"), _config(mode="multi_tool"))
    assert artifact.status == "completed"
    assert len(artifact.trajectory) == 5
    assert artifact.trajectory[0].type == "tool_call"
    assert artifact.trajectory[0].tool == "search"
    assert artifact.trajectory[2].type == "tool_call"
    assert artifact.trajectory[2].tool == "get_forecast"


def test_langgraph_no_tools() -> None:
    from evalforge.adapters.langgraph import LangGraphAdapter

    adapter = LangGraphAdapter()
    artifact = adapter.run(_scenario(mode="no_tool"), _config(mode="no_tool"))
    assert artifact.status == "completed"
    assert artifact.output.final == "I don't have enough information to answer."
    assert len(artifact.trajectory) == 1
    assert artifact.trajectory[0].type == "response"


def test_langgraph_missing_module() -> None:
    from evalforge.adapters.langgraph import LangGraphAdapter

    config = _config()
    config["module"] = "nonexistent.module"
    adapter = LangGraphAdapter()
    artifact = adapter.run(_scenario(), config)
    assert artifact.status == "error"
    err = (artifact.error or "").lower()
    assert "langgraph" in err or "extra" in err


def test_langgraph_empty_trajectory() -> None:
    from evalforge.adapters.langgraph import LangGraphAdapter

    adapter = LangGraphAdapter()
    scenario = Scenario(
        id="sc-empty", title="Empty", input="hi", context={"mode": "empty_trajectory"}
    )
    config = {"module": "fixtures.langgraph_agent", "run_id": "r1", "timeout_seconds": 10}
    artifact = adapter.run(scenario, config)
    # A blank completion (no output) must be treated as an error, not a pass.
    assert artifact.status == "error"
    assert "blank completion" in (artifact.error or "")
    assert len(artifact.trajectory) == 0
