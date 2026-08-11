import pytest

from evalforge.adapters.factory import create_adapter
from evalforge.adapters.http import HttpAdapter
from evalforge.adapters.pydantic_ai import PydanticAIAdapter
from evalforge.adapters.python_import import PythonImportAdapter
from evalforge.adapters.subprocess import SubprocessAdapter


def test_create_subprocess() -> None:
    assert isinstance(create_adapter({"type": "subprocess", "command": "echo"}), SubprocessAdapter)


def test_create_python() -> None:
    assert isinstance(create_adapter({"type": "python", "module": "x"}), PythonImportAdapter)


def test_create_http() -> None:
    assert isinstance(create_adapter({"type": "http", "url": "http://x"}), HttpAdapter)


def test_create_pydantic_ai() -> None:
    assert isinstance(create_adapter({"type": "pydantic-ai", "module": "x"}), PydanticAIAdapter)


def test_create_langgraph() -> None:
    from evalforge.adapters.langgraph import LangGraphAdapter
    assert isinstance(create_adapter({"type": "langgraph", "module": "x"}), LangGraphAdapter)


def test_create_crewai() -> None:
    from evalforge.adapters.crewai import CrewAIAdapter
    assert isinstance(create_adapter({"type": "crewai", "module": "x"}), CrewAIAdapter)


def test_create_openai_agents() -> None:
    from evalforge.adapters.openai_agents import OpenAIAgentsAdapter
    assert isinstance(
        create_adapter({"type": "openai-agents", "module": "x"}), OpenAIAgentsAdapter
    )


def test_create_smolagents() -> None:
    from evalforge.adapters.smolagents import SmolagentsAdapter
    assert isinstance(create_adapter({"type": "smolagents", "module": "x"}), SmolagentsAdapter)


def test_create_autogen() -> None:
    from evalforge.adapters.autogen import AutoGenAdapter
    assert isinstance(create_adapter({"type": "autogen", "module": "x"}), AutoGenAdapter)


def test_create_llamaindex() -> None:
    from evalforge.adapters.llamaindex import LlamaIndexAdapter
    assert isinstance(create_adapter({"type": "llamaindex", "module": "x"}), LlamaIndexAdapter)


def test_create_claude() -> None:
    from evalforge.adapters.claude import ClaudeAgentSDKAdapter
    assert isinstance(create_adapter({"type": "claude", "module": "x"}), ClaudeAgentSDKAdapter)


def test_create_adk() -> None:
    from evalforge.adapters.adk import ADKAdapter
    assert isinstance(create_adapter({"type": "adk", "module": "x"}), ADKAdapter)


def test_unknown_type_raises() -> None:
    with pytest.raises(ValueError, match="unknown adapter type"):
        create_adapter({"type": "nope"})
