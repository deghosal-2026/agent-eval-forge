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