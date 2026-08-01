# M6: Framework Adapters — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship LangGraph and PydanticAI adapters that auto-extract trajectory from framework internals, with example agents, tests, and docs.

**Architecture:** Two new `Adapter` subclasses (`LangGraphAdapter`, `PydanticAIAdapter`) registered in the existing factory. Each imports the user's module, calls `build_agent(payload)` to get a framework-specific agent, invokes it with scenario input, and auto-extracts trajectory from the framework's native result structures.

**Tech Stack:** Python 3.11+, pydantic >=2.7, langgraph >=0.2 (optional), pydantic-ai >=0.0.10 (optional)

## Global Constraints

- All adapter files go in `src/evalforge/adapters/`
- All test files go in `tests/test_adapters_*.py`
- All fixture agents go in `tests/fixtures/*.py`
- Example agents go in `examples/*.py`
- Adapter docs go in `docs/adapters/*.md`
- Optional dependencies (`langgraph`, `pydantic-ai`) imported lazily inside `_invoke()` — guarded import with clear error message
- Adapters are stateless — no constructor args (see `factory.py` line 32)
- Adapters must implement `_invoke(self, payload, config) -> str | dict` returning a `evalforge.run_envelope.v1` envelope dict
- Adapter `name` class attribute must be set (used for artifact tracking)
- Run tests via `uv run python -m pytest`
- No model API keys in tests — fixture agents must not call any real LLM
- Base commit for review package: HEAD of main after design doc commit

---
## File Structure

| Action | File | Purpose |
|---|---|---|
| Create | `src/evalforge/adapters/langgraph.py` | `LangGraphAdapter` — imports user module, invokes CompiledGraph, extracts trajectory from messages |
| Create | `src/evalforge/adapters/pydantic_ai.py` | `PydanticAIAdapter` — imports user module, invokes Agent.run_sync(), extracts trajectory from all_messages() |
| Modify | `src/evalforge/adapters/factory.py` | Register both adapters in `ADAPTERS` dict + add imports |
| Modify | `src/evalforge/adapters/__init__.py` | Export new adapter classes |
| Create | `tests/fixtures/langgraph_agent.py` | Test stub: exports `build_agent(payload)` returning mock with `.invoke()` |
| Create | `tests/fixtures/pydantic_ai_agent.py` | Test stub: exports `build_agent(payload)` returning mock with `.run_sync()` |
| Create | `tests/test_adapters_langgraph.py` | LangGraph adapter unit tests |
| Create | `tests/test_adapters_pydantic_ai.py` | PydanticAI adapter unit tests |
| Create | `tests/test_adapters_integration.py` | Integration tests: launch scenarios 1-5 through both adapters |
| Create | `examples/langgraph_agent.py` | Runnable example: `create_react_agent` with tools |
| Create | `examples/pydantic_ai_agent.py` | Runnable example: `pydantic_ai.Agent` with tools |
| Create | `docs/adapters/langgraph.md` | LangGraph adapter docs |
| Create | `docs/adapters/pydantic-ai.md` | PydanticAI adapter docs |
| Modify | `docs/wbs.md` | Mark M6 checklist items |
| Modify | `CHANGELOG.md` | Add M6 entries |

### Task 1: LangGraph fixture agent

**Files:**
- Create: `tests/fixtures/langgraph_agent.py`

**Interfaces:**
- Produces: module with `build_agent(payload) -> object` where object has `.invoke(state) -> dict` returning `{"messages": [msg1, msg2, ...]}` with messages shaped like LangChain BaseMessage objects (have `.type`, `.content`, optionally `.tool_calls` and `.name`/`.tool_call_id`).

- [ ] **Step 1: Create the fixture agent module**

`tests/fixtures/langgraph_agent.py`:
```python
"""Mock LangGraph agent for adapter tests.

Exports ``build_agent(payload)`` which returns a mock agent whose
``.invoke(state)`` produces a message list mimicking ``create_react_agent``
output. Modes are driven by payload context context["mode"]:

- ``tool_call``: one tool call + result + final response
- ``multi_tool``: two tool calls + results + final response
- ``no_tool``: final response only (no tool calls)
- ``empty_trajectory``: single response with no tools
"""

from types import SimpleNamespace


def _msg(
    type_: str,
    content: str,
    tool_calls: list | None = None,
    name: str | None = None,
    tool_call_id: str | None = None,
) -> SimpleNamespace:
    ns = SimpleNamespace(type=type_, content=content)
    if tool_calls:
        ns.tool_calls = tool_calls
    if name:
        ns.name = name
    if tool_call_id:
        ns.tool_call_id = tool_call_id
    return ns


def _tool_call(name: str, args: dict, tool_call_id: str) -> SimpleNamespace:
    return _msg("ai", "", tool_calls=[{"name": name, "args": args, "id": tool_call_id}])


def build_agent(payload: dict) -> object:
    """Build a mock agent that returns predefined message sequences."""
    mode = payload.get("context", {}).get("mode", "tool_call")
    values: dict[str, list] = {
        "tool_call": [
            _tool_call("get_weather", {"city": "London"}, "call_1"),
            _msg("tool", '{"temp": 15}', name="get_weather", tool_call_id="call_1"),
            _msg("ai", "The weather in London is 15\u00b0C."),
        ],
        "multi_tool": [
            _tool_call("search", {"q": "weather"}, "call_1"),
            _msg("tool", "sunny", name="search", tool_call_id="call_1"),
            _tool_call("get_forecast", {"day": "tomorrow"}, "call_2"),
            _msg("tool", '{"high": 20}', name="get_forecast", tool_call_id="call_2"),
            _msg("ai", "Tomorrow will be sunny with a high of 20\u00b0C."),
        ],
        "no_tool": [
            _msg("ai", "I don't have enough information to answer."),
        ],
        "tool_result": [],  # passthrough — uses same as tool_call
    }
    msgs = values.get(mode, values["tool_call"])
    return SimpleNamespace(
        invoke=lambda state: {"messages": msgs},
        name="langgraph_mock_agent",
    )
```

- [ ] **Step 2: Run a quick import check**

Run: `uv run python -c "from tests.fixtures.langgraph_agent import build_agent; agent = build_agent({'context': {'mode': 'tool_call'}, 'input': 'hi'}); r = agent.invoke({}); print(len(r['messages']))"`
Expected: `3`

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/langgraph_agent.py
git commit -m "test(m6): add LangGraph mock fixture agent for adapter tests"
```

---
### Task 2: LangGraphAdapter — tests + implementation

**Files:**
- Create: `src/evalforge/adapters/langgraph.py`
- Create: `tests/test_adapters_langgraph.py`
- Modify: `src/evalforge/adapters/factory.py` (register LangGraphAdapter)
- Modify: `src/evalforge/adapters/__init__.py` (export LangGraphAdapter)

**Interfaces:**
- Consumes: `tests/fixtures/langgraph_agent.py` (Task 1)
- Produces: `LangGraphAdapter` class with `name = "langgraph"` and `_invoke(payload, config)` returning envelope dict

- [ ] **Step 1: Write the failing tests**

`tests/test_adapters_langgraph.py`:
```python
from pathlib import Path

from evalforge.models.pack import Scenario

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
    assert "langgraph" in (artifact.error or "").lower() or "extra" in (artifact.error or "").lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_adapters_langgraph.py -v`
Expected: FAIL — "cannot import name 'LangGraphAdapter'"

- [ ] **Step 3: Implement LangGraphAdapter**

`src/evalforge/adapters/langgraph.py`:
```python
from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

from evalforge.adapters.base import Adapter
from evalforge.models.errors import AdapterError


class LangGraphAdapter(Adapter):
    name = "langgraph"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        module_name = config.get("module")
        if not module_name:
            raise AdapterError("langgraph adapter requires `module` in config")

        function_name = config.get("function", "build_agent")
        model_override = config.get("model")

        try:
            mod = importlib.import_module(module_name)
        except ImportError as exc:
            raise AdapterError(
                f"cannot import module '{module_name}': {exc}. "
                "If this is a langgraph agent, install with: pip install evalforge[langgraph]"
            ) from exc

        try:
            builder = getattr(mod, function_name)
        except AttributeError as exc:
            raise AdapterError(
                f"module '{module_name}' has no function '{function_name}'"
            ) from exc

        try:
            kwargs: dict[str, Any] = {}
            if model_override:
                kwargs["model"] = model_override
            agent = builder(payload, **kwargs)
        except Exception as exc:
            raise AdapterError(f"build_agent failed: {exc}") from exc

        if not hasattr(agent, "invoke"):
            raise AdapterError(
                "build_agent must return an object with an .invoke() method"
            )

        user_input = payload.get("input", "")
        initial_state = {"messages": [{"role": "user", "content": user_input}]}

        try:
            result = agent.invoke(initial_state)
        except Exception as exc:
            raise AdapterError(f"agent invocation failed: {exc}") from exc

        if not isinstance(result, dict) or "messages" not in result:
            raise AdapterError("agent result missing 'messages' key")

        messages = result["messages"]
        steps, final_content = _extract_trajectory(messages)

        return {
            "schema_version": "evalforge.run_envelope.v1",
            "status": "completed",
            "output": {"final": final_content, "structured": None},
            "trajectory": {"steps": steps},
            "cost": None,
            "error": None,
        }


def _extract_trajectory(
    messages: list[Any],
) -> tuple[list[dict[str, Any]], str | None]:
    steps: list[dict[str, Any]] = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                steps.append({
                    "type": "tool_call",
                    "tool": tc["name"],
                    "args": tc.get("args", {}),
                    "duration_ms": None,
                })
        elif getattr(msg, "type", None) == "tool":
            steps.append({
                "type": "tool_result",
                "tool": getattr(msg, "name", msg.tool_call_id) or "",
                "result": getattr(msg, "content", ""),
                "duration_ms": None,
            })

    final_content: str | None = None
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai" and not getattr(msg, "tool_calls", None):
            final_content = getattr(msg, "content", None) or ""
            break

    if final_content is not None:
        steps.append({
            "type": "response",
            "content": final_content,
            "duration_ms": None,
        })

    return steps, final_content
```

- [ ] **Step 4: Register in factory.py**

Edit `src/evalforge/adapters/factory.py`:
- Add import: `from evalforge.adapters.langgraph import LangGraphAdapter`
- Add to `ADAPTERS` dict: `"langgraph": LangGraphAdapter,`

- [ ] **Step 5: Export in __init__.py**

Edit `src/evalforge/adapters/__init__.py`:
- Add import: `from evalforge.adapters.langgraph import LangGraphAdapter`
- Add to `__all__`: `"LangGraphAdapter",`

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_adapters_langgraph.py -v`
Expected: PASS — all 4 tests

- [ ] **Step 7: Commit**

```bash
git add src/evalforge/adapters/langgraph.py tests/test_adapters_langgraph.py src/evalforge/adapters/factory.py src/evalforge/adapters/__init__.py
git commit -m "feat(m6): add LangGraph adapter with auto-trajectory extraction"
```

---
### Task 3: PydanticAI fixture agent

**Files:**
- Create: `tests/fixtures/pydantic_ai_agent.py`

**Interfaces:**
- Produces: module with `build_agent(payload) -> object` where object has `.run_sync(input) -> result` and result has `.all_messages() -> list` and `.data -> Any`

- [ ] **Step 1: Create the fixture agent module**

`tests/fixtures/pydantic_ai_agent.py`:
```python
"""Mock PydanticAI agent for adapter tests.

Exports ``build_agent(payload)`` which returns a mock agent whose
``.run_sync(input)`` returns a result mimicking ``pydantic_ai.Agent`` output.
Modes driven by payload context["mode"]:

- ``tool_call``: one tool call + result + final response
- ``no_tool``: final response only
- ``structured``: returns structured data (dict) as result.data
"""

from types import SimpleNamespace


def _part(kind: str, **kwargs: object) -> SimpleNamespace:
    ns = SimpleNamespace(**kwargs)
    ns.kind = lambda: kind
    return ns


def build_agent(payload: dict) -> object:
    mode = payload.get("context", {}).get("mode", "tool_call")
    user_input = payload.get("input", "")

    if mode == "no_tool":
        data = "I have no tools available."
        messages = [SimpleNamespace(
            parts=[_part("final", content=data)],
            role="assistant",
        )]
    elif mode == "structured":
        data = {"temperature": 15, "condition": "sunny"}
        messages = [
            SimpleNamespace(
                parts=[_part("tool-call", tool_name="get_weather",
                             args={"city": "London"})],
                role="assistant",
            ),
            SimpleNamespace(
                parts=[_part("tool-return", tool_name="get_weather",
                             content={"temp": 15})],
                role="tool",
            ),
            SimpleNamespace(
                parts=[_part("final", content=str(data))],
                role="assistant",
            ),
        ]
    else:
        data = "The weather in London is 15\u00b0C."
        messages = [
            SimpleNamespace(
                parts=[_part("tool-call", tool_name="get_weather",
                             args={"city": "London"})],
                role="assistant",
            ),
            SimpleNamespace(
                parts=[_part("tool-return", tool_name="get_weather",
                             content={"temp": 15})],
                role="tool",
            ),
            SimpleNamespace(
                parts=[_part("final", content=data)],
                role="assistant",
            ),
        ]

    result = SimpleNamespace(all_messages=lambda: messages, data=data)
    return SimpleNamespace(run_sync=lambda input_str: result, name="pydanticai_mock")
```

- [ ] **Step 2: Quick import check**

Run: `uv run python -c "from tests.fixtures.pydantic_ai_agent import build_agent; agent = build_agent({'context': {'mode': 'tool_call'}, 'input': 'hi'}); r = agent.run_sync('hi'); print(len(r.all_messages()))"`
Expected: `3`

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/pydantic_ai_agent.py
git commit -m "test(m6): add PydanticAI mock fixture agent for adapter tests"
```

---
### Task 4: PydanticAIAdapter — tests + implementation

**Files:**
- Create: `src/evalforge/adapters/pydantic_ai.py`
- Create: `tests/test_adapters_pydantic_ai.py`
- Modify: `src/evalforge/adapters/factory.py` (register PydanticAIAdapter)
- Modify: `src/evalforge/adapters/__init__.py` (export PydanticAIAdapter)

**Interfaces:**
- Consumes: `tests/fixtures/pydantic_ai_agent.py` (Task 3)
- Produces: `PydanticAIAdapter` class with `name = "pydantic-ai"` and `_invoke(payload, config)` returning envelope dict

- [ ] **Step 1: Write the failing tests**

`tests/test_adapters_pydantic_ai.py`:
```python
from evalforge.models.pack import Scenario
from evalforge.adapters.pydantic_ai import PydanticAIAdapter


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_adapters_pydantic_ai.py -v`
Expected: FAIL — "cannot import name 'PydanticAIAdapter'"

- [ ] **Step 3: Implement PydanticAIAdapter**

`src/evalforge/adapters/pydantic_ai.py`:
```python
from __future__ import annotations

import importlib
from typing import Any

from evalforge.adapters.base import Adapter
from evalforge.models.errors import AdapterError


class PydanticAIAdapter(Adapter):
    name = "pydantic-ai"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        module_name = config.get("module")
        if not module_name:
            raise AdapterError("pydantic-ai adapter requires `module` in config")

        function_name = config.get("function", "build_agent")
        model_override = config.get("model")

        try:
            mod = importlib.import_module(module_name)
        except ImportError as exc:
            raise AdapterError(
                f"cannot import module '{module_name}': {exc}. "
                "If this is a pydantic-ai agent, install with: pip install evalforge[pydanticai]"
            ) from exc

        try:
            builder = getattr(mod, function_name)
        except AttributeError as exc:
            raise AdapterError(
                f"module '{module_name}' has no function '{function_name}'"
            ) from exc

        try:
            kwargs: dict[str, Any] = {}
            if model_override:
                kwargs["model"] = model_override
            agent = builder(payload, **kwargs)
        except Exception as exc:
            raise AdapterError(f"build_agent failed: {exc}") from exc

        if not hasattr(agent, "run_sync"):
            raise AdapterError(
                "build_agent must return an object with a .run_sync() method"
            )

        user_input = payload.get("input", "")

        try:
            result = agent.run_sync(user_input)
        except Exception as exc:
            raise AdapterError(f"agent invocation failed: {exc}") from exc

        all_messages = result.all_messages() if hasattr(result, "all_messages") else []
        steps, final_content = _extract_trajectory(all_messages)

        structured = getattr(result, "data", None)
        if structured is not None and not isinstance(structured, str):
            final_content = final_content or str(structured)

        return {
            "schema_version": "evalforge.run_envelope.v1",
            "status": "completed",
            "output": {"final": final_content, "structured": structured if isinstance(structured, dict) else None},
            "trajectory": {"steps": steps},
            "cost": _extract_cost(result),
            "error": None,
        }


def _extract_trajectory(
    all_messages: list[Any],
) -> tuple[list[dict[str, Any]], str | None]:
    steps: list[dict[str, Any]] = []
    final_content: str | None = None

    for msg in all_messages:
        parts = getattr(msg, "parts", [])
        if not parts:
            continue
        for part in parts:
            kind = part.kind() if hasattr(part, "kind") else ""
            if kind == "tool-call":
                steps.append({
                    "type": "tool_call",
                    "tool": getattr(part, "tool_name", ""),
                    "args": getattr(part, "args", {}),
                    "duration_ms": None,
                })
            elif kind == "tool-return":
                steps.append({
                    "type": "tool_result",
                    "tool": getattr(part, "tool_name", ""),
                    "result": getattr(part, "content", None),
                    "duration_ms": None,
                })
            elif kind == "final":
                final_content = getattr(part, "content", "") or ""

    if final_content:
        steps.append({
            "type": "response",
            "content": final_content,
            "duration_ms": None,
        })

    return steps, final_content


def _extract_cost(result: Any) -> dict[str, Any] | None:
    """Extract usage/cost if the result has a .usage() method (pydantic-ai >=0.0.10)."""
    if hasattr(result, "usage"):
        try:
            usage = result.usage()
            if usage is not None:
                return {
                    "input_tokens": getattr(usage, "request_tokens", 0),
                    "output_tokens": getattr(usage, "response_tokens", 0),
                    "total_tokens": getattr(usage, "total_tokens", 0),
                    "cost_usd": 0.0,
                }
        except Exception:
            pass
    return None
```

- [ ] **Step 4: Register in factory.py**

Edit `src/evalforge/adapters/factory.py`:
- Add import: `from evalforge.adapters.pydantic_ai import PydanticAIAdapter`
- Add to `ADAPTERS` dict: `"pydantic-ai": PydanticAIAdapter,`

- [ ] **Step 5: Export in __init__.py**

Edit `src/evalforge/adapters/__init__.py`:
- Add import: `from evalforge.adapters.pydantic_ai import PydanticAIAdapter`
- Add to `__all__`: `"PydanticAIAdapter",`

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_adapters_langgraph.py tests/test_adapters_pydantic_ai.py -v`
Expected: PASS — all 4 langgraph + 4 pydantic_ai tests

- [ ] **Step 7: Run factory test**

Run: `uv run python -m pytest tests/test_adapters_factory.py -v`
Expected: PASS — existing 4 tests + new types resolve correctly. May need to update factory test to cover new types.

- [ ] **Step 8: Commit**

```bash
git add src/evalforge/adapters/pydantic_ai.py tests/test_adapters_pydantic_ai.py src/evalforge/adapters/factory.py src/evalforge/adapters/__init__.py
git commit -m "feat(m6): add PydanticAI adapter with auto-trajectory extraction"
```

---
### Task 5: Example agents

**Files:**
- Create: `examples/langgraph_agent.py`
- Create: `examples/pydantic_ai_agent.py`

- [ ] **Step 1: Create LangGraph example agent**

`examples/langgraph_agent.py`:
```python
"""Example LangGraph agent for use with the LangGraphAdapter.

Usage:
    uv run python examples/langgraph_agent.py

To use with the adapter in a config:
    {"type": "langgraph", "module": "examples.langgraph_agent", "model": "..."}
"""

import json
from typing import Any

from langgraph.prebuilt import create_react_agent

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"],
        },
    },
]


def build_agent(payload: dict[str, Any], model: str | None = None) -> Any:
    """Build a prebuilt ReAct agent for the given scenario payload."""
    model_name = model or "openai:gpt-4o-mini"
    tools = payload.get("allowed_tools", TOOLS)
    agent = create_react_agent(model_name, tools=tools)
    return agent


if __name__ == "__main__":
    payload = {"input": "What is the weather in London?", "allowed_tools": TOOLS}
    agent = build_agent(payload)
    result = agent.invoke({"messages": [{"role": "user", "content": payload["input"]}]})
    for msg in result["messages"]:
        print(f"{msg.type}: {getattr(msg, 'content', '')}")
```

- [ ] **Step 2: Create PydanticAI example agent**

`examples/pydantic_ai_agent.py`:
```python
"""Example PydanticAI agent for use with the PydanticAIAdapter.

Usage:
    uv run python examples/pydantic_ai_agent.py

To use with the adapter in a config:
    {"type": "pydantic-ai", "module": "examples.pydantic_ai_agent", "model": "..."}
"""

from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent, RunContext


@dataclass
class WeatherResult:
    temperature: float
    condition: str
    city: str


weather_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=WeatherResult,
    system_prompt="You are a helpful weather assistant.",
)


@weather_agent.tool_plain
def get_weather(city: str) -> dict[str, Any]:
    """Get the weather for a city."""
    return {"temperature": 15, "condition": "sunny", "city": city}


def build_agent(payload: dict[str, Any], model: str | None = None) -> Any:
    """Build a PydanticAI agent for the given scenario payload."""
    return weather_agent


if __name__ == "__main__":
    import asyncio

    result = asyncio.run(weather_agent.run("What is the weather in London?"))
    print(f"Final: {result.data}")
    for msg in result.all_messages():
        print(f"Message: {msg}")
```

- [ ] **Step 3: Verify example agents are syntactically valid**

Run: `uv run python -c "import ast; ast.parse(open('examples/langgraph_agent.py').read()); print('langgraph: OK')"`
Run: `uv run python -c "import ast; ast.parse(open('examples/pydantic_ai_agent.py').read()); print('pydantic_ai: OK')"`
Expected: Both print "OK"

- [ ] **Step 4: Commit**

```bash
git add examples/langgraph_agent.py examples/pydantic_ai_agent.py
git commit -m "docs(m6): add example agents for LangGraph and PydanticAI"
```

---
### Task 6: Integration tests

**Files:**
- Create: `tests/test_adapters_integration.py`

- [ ] **Step 1: Write the integration tests**

`tests/test_adapters_integration.py`:
```python
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
```

- [ ] **Step 2: Run integration tests (should be skipped — deps not installed)**

Run: `uv run python -m pytest tests/test_adapters_integration.py -v`
Expected: SKIP (both tests skipped due to missing langgraph/pydantic-ai)

- [ ] **Step 3: Commit**

```bash
git add tests/test_adapters_integration.py
git commit -m "test(m6): add integration tests for adapters (skipped without optional deps)"
```

---
### Task 7: Documentation + WBS + CHANGELOG

**Files:**
- Create: `docs/adapters/langgraph.md`
- Create: `docs/adapters/pydantic-ai.md`
- Modify: `docs/wbs.md` (mark M6 items)
- Modify: `CHANGELOG.md` (add M6 entries)

- [ ] **Step 1: Create LangGraph adapter docs**

`docs/adapters/langgraph.md`:
```markdown
# LangGraph Adapter

## Overview

The `langgraph` adapter invokes a LangGraph `create_react_agent` compiled graph,
then automatically extracts the trajectory (tool calls, tool results, final
response) from the graph's message history. You write a natural LangGraph agent;
the adapter handles the EvalForge run envelope contract.

## Installation

```bash
pip install evalforge[langgraph]
```

## Agent Contract

Your Python module must export a `build_agent(payload, model=None)` function:

```python
from langgraph.prebuilt import create_react_agent

def build_agent(payload, model=None):
    """Return a CompiledGraph (via create_react_agent)."""
    tools = payload.get("allowed_tools", [])
    agent = create_react_agent(model or "openai:gpt-4o-mini", tools=tools)
    return agent
```

The `payload` dict contains: `input`, `context`, `allowed_tools`,
`disallowed_tools`, `budget` (scenario fields, minus `expected` and `metrics`).

## Configuration

| Key | Required | Default | Description |
|---|---|---|---|
| `type` | Yes | — | Must be `"langgraph"` |
| `module` | Yes | — | Dotted Python module path |
| `function` | No | `"build_agent"` | Function name in the module |
| `model` | No | None | Override the LLM model name |
| `timeout_seconds` | No | 120 | Agent invocation timeout |

## Example

```yaml
# evalforge config
agent:
  type: langgraph
  module: examples.langgraph_agent
  function: build_agent
  model: anthropic:claude-sonnet-4-20250514
```

## Trajectory Mapping

| LangGraph Message | EvalForge Step |
|---|---|
| `AIMessage` with `tool_calls` | `tool_call` (one per tool call) |
| `ToolMessage` | `tool_result` |
| Final `AIMessage` without tool_calls | `response` |

## Error Handling

| Problem | Result |
|---|---|
| Module not found | `AdapterError` — suggests `pip install evalforge[langgraph]` |
| `build_agent` fails | `AdapterError` with original exception |
| Agent returns unexpected structure | `AdapterError` with diagnostic |
| Invocation timeout | `AgentTimeoutError` → artifact `status="timeout"` |
```

- [ ] **Step 2: Create PydanticAI adapter docs**

`docs/adapters/pydantic-ai.md`:
```markdown
# PydanticAI Adapter

## Overview

The `pydantic-ai` adapter invokes a PydanticAI Agent, then automatically
extracts the trajectory (tool calls, tool results, final response) from the
agent's message history and captures structured output. You write a natural
PydanticAI agent; the adapter handles the EvalForge run envelope contract.

## Installation

```bash
pip install evalforge[pydanticai]
```

## Agent Contract

Your Python module must export a `build_agent(payload, model=None)` function:

```python
from pydantic_ai import Agent

def build_agent(payload, model=None):
    """Return a pydantic_ai Agent."""
    agent = Agent(model or "openai:gpt-4o-mini")
    return agent
```

The `payload` dict contains: `input`, `context`, `allowed_tools`,
`disallowed_tools`, `budget`.

## Configuration

| Key | Required | Default | Description |
|---|---|---|---|
| `type` | Yes | — | Must be `"pydantic-ai"` |
| `module` | Yes | — | Dotted Python module path |
| `function` | No | `"build_agent"` | Function name in the module |
| `model` | No | None | Override the LLM model name |
| `timeout_seconds` | No | 120 | Agent invocation timeout |

## Example

```yaml
# evalforge config
agent:
  type: pydantic-ai
  module: examples.pydantic_ai_agent
  function: build_agent
```

## Trajectory Mapping

| PydanticAI Part | EvalForge Step |
|---|---|
| `ToolCallPart` | `tool_call` |
| `ToolReturnPart` | `tool_result` |
| Final `final` part | `response` |

## Structured Output

If your agent uses a typed result type, the adapter captures `result.data` in
the artifact's `output.structured` field. The `output.final` is set to
`str(result.data)`.

## Cost Extraction

If the agent result provides `.usage()`, the adapter extracts token counts for
the artifact. Otherwise, `cost` defaults to zero.

## Error Handling

| Problem | Result |
|---|---|
| Module not found | `AdapterError` — suggests `pip install evalforge[pydanticai]` |
| `build_agent` fails | `AdapterError` with original exception |
| Invocation timeout | `AgentTimeoutError` → artifact `status="timeout"` |
```

- [ ] **Step 3: Update WBS**

Edit `docs/wbs.md` M6 checklist — mark tasks as `[x]`:
- Design doc (already checked)
- LangGraph adapter implementation
- PydanticAI adapter implementation
- Example agents
- Integration tests
- Adapter documentation

- [ ] **Step 4: Update CHANGELOG**

Add under `## [Unreleased]`:
```markdown
### Added
- M6: LangGraph adapter (`langgraph` type) — auto-extracts trajectory from `create_react_agent` message history
- M6: PydanticAI adapter (`pydantic-ai` type) — auto-extracts trajectory and structured output from `Agent.run_sync()`
- M6: Example agents for both frameworks (`examples/`)
- M6: Integration tests — parametrized over launch scenarios 1-5 (skipped without optional deps)
- M6: Adapter documentation (`docs/adapters/`)
```

- [ ] **Step 5: Verify exit gates**

Run: `uv run python -m pytest -q`
Expected: all existing tests + new tests pass

Run: `uv run ruff check .`
Expected: zero errors

Run: `uv run mypy --strict`
Expected: zero errors (mypy is scoped to `src/`; adapter code must type-check)

- [ ] **Step 6: Commit**

```bash
git add docs/adapters/ CHANGELOG.md
git commit -m "docs(m6): add adapter documentation, update WBS and changelog"
```

---
## Self-Review

**1. Spec coverage:** Each design doc section maps to a task — LangGraph fixture + adapter (T1+T2), PydanticAI fixture + adapter (T3+T4), example agents (T5), integration tests (T6), docs and WBS (T7). Factory registration and `__init__.py` exports are included in each adapter's task.

**2. Placeholder scan:** No TBD/TODO. Every code block is complete. Every step contains concrete commands and assertions.

**3. Type consistency:** `build_agent(payload, model=None)` — same signature for both adapters. `_invoke` returns `dict[str, Any]` envelope (matches `Adapter` base class). Trajectory dicts use the same keys as `_tool_call`/`_tool_result` helpers in `launch_agents.py`. `_extract_cost` returns `dict[str, Any] | None` matching the envelope's `cost` field.