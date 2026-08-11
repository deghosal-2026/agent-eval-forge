"""Integration tests running launch scenarios 1-5 through both new adapters.

These tests verify that each adapter can produce a valid RunArtifact for
real launch scenarios. They are skipped if the optional framework dependency
is not installed (no model API keys needed — the fixture agents are mock-only).
"""

import importlib

import pytest

from evalforge.adapters.langgraph import LangGraphAdapter
from evalforge.adapters.pydantic_ai import PydanticAIAdapter
from evalforge.models.pack import Scenario

_LANGGRAPH_AVAILABLE = importlib.util.find_spec("langgraph") is not None
_PYDANTIC_AI_AVAILABLE = importlib.util.find_spec("pydantic_ai") is not None
_CREWAI_AVAILABLE = importlib.util.find_spec("crewai") is not None
_OPENAI_AGENTS_AVAILABLE = importlib.util.find_spec("agents") is not None
_SMOLAGENTS_AVAILABLE = importlib.util.find_spec("smolagents") is not None
_AUTOGEN_AVAILABLE = importlib.util.find_spec("autogen_agentchat") is not None
_LLAMAINDEX_AVAILABLE = importlib.util.find_spec("llama_index") is not None
_CLAUDE_AVAILABLE = importlib.util.find_spec("claude_agent_sdk") is not None
_ADK_AVAILABLE = importlib.util.find_spec("google.adk") is not None

M4_SCENARIO_IDS = [
    "launch-01-account-policy",
    "launch-01-system-status",
    "launch-02-cross-source",
    "launch-02-incident-context",
    "launch-03-incident-extraction",
    "launch-03-config-extraction",
    "launch-04-deploy-args",
    "launch-04-time-range-args",
    "launch-05-prod-delete-refusal",
    "launch-05-staging-vs-prod-refusal",
]


@pytest.mark.skipif(not _LANGGRAPH_AVAILABLE, reason="langgraph not installed")
@pytest.mark.parametrize("scenario_id", M4_SCENARIO_IDS)
def test_langgraph_adapter_produces_valid_artifact(scenario_id: str) -> None:
    scenario = Scenario(
        id=scenario_id,
        title=scenario_id,
        input="test input for " + scenario_id,
        context={"mode": "tool_call"},
    )
    config = {
        "module": "fixtures.langgraph_agent",
        "run_id": "int-1",
        "timeout_seconds": 10,
    }
    adapter = LangGraphAdapter()
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.id == "int-1-" + scenario_id
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _PYDANTIC_AI_AVAILABLE, reason="pydantic-ai not installed")
@pytest.mark.parametrize("scenario_id", M4_SCENARIO_IDS)
def test_pydantic_ai_adapter_produces_valid_artifact(scenario_id: str) -> None:
    scenario = Scenario(
        id=scenario_id,
        title=scenario_id,
        input="test input for " + scenario_id,
        context={"mode": "tool_call"},
    )
    config = {
        "module": "fixtures.pydantic_ai_agent",
        "run_id": "int-1",
        "timeout_seconds": 10,
    }
    adapter = PydanticAIAdapter()
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.id == "int-1-" + scenario_id
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _CREWAI_AVAILABLE, reason="crewai not installed")
@pytest.mark.parametrize("scenario_id", M4_SCENARIO_IDS)
def test_crewai_adapter_produces_valid_artifact(scenario_id: str) -> None:
    from evalforge.adapters.crewai import CrewAIAdapter

    scenario = Scenario(
        id=scenario_id,
        title=scenario_id,
        input="test input for " + scenario_id,
        context={"mode": "tool_call"},
    )
    config = {
        "module": "fixtures.crewai_agent",
        "run_id": "int-1",
        "timeout_seconds": 10,
    }
    adapter = CrewAIAdapter()
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.id == "int-1-" + scenario_id
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _OPENAI_AGENTS_AVAILABLE, reason="openai-agents not installed")
@pytest.mark.parametrize("scenario_id", M4_SCENARIO_IDS)
def test_openai_agents_adapter_produces_valid_artifact(scenario_id: str) -> None:
    from evalforge.adapters.openai_agents import OpenAIAgentsAdapter

    scenario = Scenario(
        id=scenario_id,
        title=scenario_id,
        input="test input for " + scenario_id,
        context={"mode": "tool_call"},
    )
    config = {
        "module": "fixtures.openai_agents_agent",
        "run_id": "int-1",
        "timeout_seconds": 10,
    }
    adapter = OpenAIAgentsAdapter()
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.id == "int-1-" + scenario_id
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _SMOLAGENTS_AVAILABLE, reason="smolagents not installed")
@pytest.mark.parametrize("scenario_id", M4_SCENARIO_IDS)
def test_smolagents_adapter_produces_valid_artifact(scenario_id: str) -> None:
    from evalforge.adapters.smolagents import SmolagentsAdapter

    scenario = Scenario(
        id=scenario_id,
        title=scenario_id,
        input="test input for " + scenario_id,
        context={"mode": "tool_call"},
    )
    config = {
        "module": "fixtures.smolagents_agent",
        "run_id": "int-1",
        "timeout_seconds": 10,
    }
    adapter = SmolagentsAdapter()
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.id == "int-1-" + scenario_id
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _AUTOGEN_AVAILABLE, reason="autogen not installed")
@pytest.mark.parametrize("scenario_id", M4_SCENARIO_IDS)
def test_autogen_adapter_produces_valid_artifact(scenario_id: str) -> None:
    from evalforge.adapters.autogen import AutoGenAdapter

    scenario = Scenario(
        id=scenario_id,
        title=scenario_id,
        input="test input for " + scenario_id,
        context={"mode": "tool_call"},
    )
    config = {
        "module": "fixtures.autogen_agent",
        "run_id": "int-1",
        "timeout_seconds": 10,
    }
    adapter = AutoGenAdapter()
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.id == "int-1-" + scenario_id
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _LLAMAINDEX_AVAILABLE, reason="llamaindex not installed")
@pytest.mark.parametrize("scenario_id", M4_SCENARIO_IDS)
def test_llamaindex_adapter_produces_valid_artifact(scenario_id: str) -> None:
    from evalforge.adapters.llamaindex import LlamaIndexAdapter

    scenario = Scenario(
        id=scenario_id,
        title=scenario_id,
        input="test input for " + scenario_id,
        context={"mode": "tool_call"},
    )
    config = {
        "module": "fixtures.llamaindex_agent",
        "run_id": "int-1",
        "timeout_seconds": 10,
    }
    adapter = LlamaIndexAdapter()
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.id == "int-1-" + scenario_id
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude-agent-sdk not installed")
@pytest.mark.parametrize("scenario_id", M4_SCENARIO_IDS)
def test_claude_adapter_produces_valid_artifact(scenario_id: str) -> None:
    from evalforge.adapters.claude import ClaudeAgentSDKAdapter

    scenario = Scenario(
        id=scenario_id,
        title=scenario_id,
        input="test input for " + scenario_id,
        context={"mode": "tool_call"},
    )
    config = {
        "module": "fixtures.claude_agent",
        "run_id": "int-1",
        "timeout_seconds": 10,
    }
    adapter = ClaudeAgentSDKAdapter()
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.id == "int-1-" + scenario_id
    assert len(artifact.trajectory) > 0


@pytest.mark.skipif(not _ADK_AVAILABLE, reason="google-adk not installed")
@pytest.mark.parametrize("scenario_id", M4_SCENARIO_IDS)
def test_adk_adapter_produces_valid_artifact(scenario_id: str) -> None:
    from evalforge.adapters.adk import ADKAdapter

    scenario = Scenario(
        id=scenario_id,
        title=scenario_id,
        input="test input for " + scenario_id,
        context={"mode": "tool_call"},
    )
    config = {
        "module": "fixtures.adk_agent",
        "run_id": "int-1",
        "timeout_seconds": 10,
    }
    adapter = ADKAdapter()
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.id == "int-1-" + scenario_id
    assert len(artifact.trajectory) > 0
