"""Agent adapters for invoking agents across runtimes (subprocess, import, HTTP, frameworks).

An adapter is the single seam between EvalForge and "your agent". It turns a
scenario (input + tools + context) into a normalized `RunArtifact` --
final output plus trajectory, cost, and error metadata (spec §"Agent Adapter
Contract").

M0 ships the package layout only. The abstract contract lands in M1
(`adapters/base.py`) with subprocess / python_import / HTTP implementations;
LangGraph and PydanticAI adapters follow in M6. The adapter contract is
deliberately kept interface-stable so custom third-party adapters written
against it keep working across releases.

Exports:
    Adapter: Abstract base class for all adapters.
    IsolatedAdapter: Runs agents in isolated subprocesses.
    LangGraphAdapter: Invokes LangGraph agents via Python import.
    PydanticAIAdapter: Invokes PydanticAI agents via Python import.
    build_invocation_payload: Builds the restricted payload sent to agents.
    create_adapter: Factory function to resolve an adapter from config.
    parse_agent_stdout: Parses agent stdout as a JSON envelope.
"""

from evalforge.adapters.base import Adapter, build_invocation_payload, parse_agent_stdout
from evalforge.adapters.factory import create_adapter
from evalforge.adapters.isolated import IsolatedAdapter
from evalforge.adapters.langgraph import LangGraphAdapter
from evalforge.adapters.pydantic_ai import PydanticAIAdapter

__all__ = [
    "Adapter",
    "IsolatedAdapter",
    "LangGraphAdapter",
    "PydanticAIAdapter",
    "build_invocation_payload",
    "create_adapter",
    "parse_agent_stdout",
]
