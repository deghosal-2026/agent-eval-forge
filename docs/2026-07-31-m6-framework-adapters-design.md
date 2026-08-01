# M6: Framework Adapters — Design

**Created:** 2026-07-31
**Milestone:** M6 (Framework Adapters)
**Issues:** #81 (LangGraph adapter), #82 (PydanticAI adapter), #103 (integration tests), #108 (example agents), #116 (launch scenarios 1-5 run), #124 (trajectory capture)
**Status:** Design

---

## Overview

Add two new adapters for popular agent frameworks: LangGraph (prebuilt `create_react_agent`) and PydanticAI. Unlike the existing PythonImportAdapter (which requires the user to manually build an EvalForge run envelope), these adapters auto-extract trajectory, tool calls, and output from the framework's native result structures. The user writes natural framework code; the adapter handles the EvalForge contract.

---

## Architecture

### Files

| File | Purpose |
|---|---|
| `src/evalforge/adapters/langgraph.py` | `LangGraphAdapter` class |
| `src/evalforge/adapters/pydantic_ai.py` | `PydanticAIAdapter` class |
| `src/evalforge/adapters/factory.py` | Register both in `ADAPTERS` dict |
| `tests/test_adapters_langgraph.py` | Unit tests for LangGraph adapter |
| `tests/test_adapters_pydantic_ai.py` | Unit tests for PydanticAI adapter |
| `tests/fixtures/langgraph_agent.py` | Test stub agent (no real LLM) |
| `tests/fixtures/pydantic_ai_agent.py` | Test stub agent (no real LLM) |
| `examples/langgraph_agent.py` | Runnable example agent |
| `examples/pydantic_ai_agent.py` | Runnable example agent |
| `docs/adapters/langgraph.md` | Adapter usage documentation |
| `docs/adapters/pydantic-ai.md` | Adapter usage documentation |

### Adapter Registration

Both adapters registered in `src/evalforge/adapters/factory.py`:

```python
ADAPTERS = {
    "subprocess": SubprocessAdapter,
    "python": PythonImportAdapter,
    "http": HttpAdapter,
    "langgraph": LangGraphAdapter,
    "pydantic-ai": PydanticAIAdapter,
}
```

### Dependency Strategy

`langgraph` and `pydantic-ai` are optional extras (already declared in `pyproject.toml`). Both adapters import lazily inside `_invoke()` using guarded imports. Import failure raises `AdapterError` with a clear message guiding the user to install the extra.

---

## Adapter Contract

### User Export

The user's Python module must export a `build_agent` function:

```python
# examples/langgraph_agent.py
from langgraph.prebuilt import create_react_agent
from langgraph.graph import CompiledGraph

def build_agent(payload: dict) -> CompiledGraph:
    """Build a prebuilt ReAct agent from the scenario payload.
    
    payload contains: input, context, allowed_tools, disallowed_tools, budget.
    The user is responsible for constructing the agent with scenario-appropriate
    tools from payload.get('allowed_tools', []).
    """
    # ... construct agent using payload context ...
    return create_react_agent(model, tools=tools)
```

### Module Resolution

Same pattern as PythonImportAdapter: config specifies `module` (dotted Python path) and `function` (default `"build_agent"`). The adapter calls `importlib.import_module(module)` then `getattr(mod, function)(payload)`.

### Config Keys

| Key | Required | Default | Description |
|---|---|---|---|
| `module` | Yes | — | Dotted Python module path (e.g. `examples.langgraph_agent`) |
| `function` | No | `"build_agent"` | Function name in that module |
| `model` | No | None | Optional model override (passed to `build_agent`) |
| `timeout_seconds` | No | 120 | Agent invocation timeout |
| `run_id` | No | `"run-unknown"` | Run identifier for the artifact |

---

## LangGraph Adapter

### Agent Construction

1. Import user module, call `function(payload)` → `CompiledGraph`
2. Pass `payload` so user can read `allowed_tools`, `disallowed_tools`, `budget`, `context`, `input` for agent construction
3. Support `model` override from config (passed as kwarg if set)

### Invocation

```python
# Build initial state for create_react_agent
user_input = payload["input"]
initial_state = {"messages": [{"role": "user", "content": user_input}]}

# Invoke the compiled graph
result = agent.invoke(initial_state)
```

### Trajectory Extraction

Walk `result["messages"]` (a list of LangChain `BaseMessage` objects):

1. **`AIMessage` with `tool_calls`** → one `tool_call` step per `tool_call` dict
2. **`ToolMessage`** → one `tool_result` step (matched by `tool_call_id` to preceding `AIMessage`)
3. **Final `AIMessage` without `tool_calls`** → one `response` step (the agent's final answer)

```python
def _extract_trajectory(messages):
    steps = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                steps.append({"type": "tool_call", "tool": tc["name"],
                              "args": tc["args"], "duration_ms": None})
        elif msg.type == "tool":
            steps.append({"type": "tool_result", "tool": msg.name,
                          "result": msg.content, "duration_ms": None})
    # Final response is the last message that is not a tool call/result
    final_content = ...
    steps.append({"type": "response", "content": final_content, "duration_ms": None})
    return steps
```

### Output Extraction

- `final` = last non-tool message content
- `structured` = None (no structured output from prebuilt agent by default)

### Error Mapping

| LangGraph Error | Adapter Error |
|---|---|
| Import error | `AdapterError("install langgraph extra")` |
| Invocation error | `AdapterError` |
| Timeout | `AgentTimeoutError` |

---

## PydanticAI Adapter

### Agent Construction

1. Import user module, call `function(payload)` → `pydantic_ai.Agent`
2. Pass `payload` for scenario-appropriate agent configuration

### Invocation

```python
user_input = payload["input"]
result = agent.run_sync(user_input)
```

### Trajectory Extraction

Walk `result.all_messages()`:

1. **`ToolCallPart` / `ToolRunPart`** in assistant messages → `tool_call` steps
2. **`ToolReturnPart` / `RetryToolPart`** → `tool_result` steps  
3. **Final assistant message content** → `response` step

```python
def _extract_trajectory(all_messages):
    steps = []
    for msg in all_messages:
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if part.kind() == "tool-call":
                    steps.append({"type": "tool_call", "tool": part.tool_name,
                                  "args": part.args, "duration_ms": None})
                elif part.kind() == "tool-return":
                    steps.append({"type": "tool_result", "tool": part.tool_name,
                                  "result": part.content, "duration_ms": None})
    return steps
```

### Output Extraction

- `final` = `str(result.data)` (the typed output converted to string)
- `structured` = `result.data` (the raw typed output, for structured-output scenarios)

### Cost Extraction

PydanticAI `result.usage()` provides token counts. If available, populate the `cost` field. Otherwise `cost=None` (defaults to zero-cost).

### Error Mapping

| PydanticAI Error | Adapter Error |
|---|---|
| Import error | `AdapterError("install pydantic-ai extra")` |
| Agent run error | `AdapterError` |
| Timeout (via concurrent.futures) | `AgentTimeoutError` |

---

## Error Handling & Edge Cases

### Common to Both

| Scenario | Behavior |
|---|---|
| `build_agent` returns wrong type | `AdapterError` |
| Agent returns unexpected shape | `AdapterError` (with diagnostic detail) |
| Module not found | `AdapterError` with install guidance |
| Invocation exceeds timeout | `AdapterError` for framework timeout → `AgentTimeoutError` by base class |
| `strict_output=True` | N/A (adapters always return dict envelope) |

### LangGraph-Specific

| Scenario | Behavior |
|---|---|
| `result["messages"]` missing | `AdapterError("missing messages key")` |
| Unknown message type | Skipped (not added to trajectory) |
| Tool call with missing name | Skipped |

### PydanticAI-Specific

| Scenario | Behavior |
|---|---|
| Known message types only | Unknown part kinds skipped |
| `result.data` has no `__str__` | Fallback to repr |

---

## Testing

### Unit Tests (no real LLM)

Each adapter test creates a `Scenario` with a known tool list, uses a minimal test fixture agent (no real model), and asserts on the returned `RunArtifact`:

1. **Envelope path** — agent returns well-formed structure → artifact has correct trajectory, output, status
2. **Error path** — `build_agent` raises → status=error, error field populated
3. **Timeout path** — agent times out → status=timeout
4. **Trajectory extraction** — agent with tool calls → correct tool_call/tool_result/response steps
5. **Message type handling** — unexpected message types skipped gracefully

### Test Fixture Agents

**`tests/fixtures/langgraph_agent.py`**: Exports `build_agent(payload)` that creates a minimal `StateGraph` (not using `create_react_agent` to avoid needing a real LLM — constructs a graph that echoes a tool call pattern).

**`tests/fixtures/pydantic_ai_agent.py`**: Exports `build_agent(payload)` that creates a `pydantic_ai.Agent` with no model (using a mock/echo pattern).

### Integration Tests

Parametrized test that runs launch scenarios 1-5 through each adapter:

```python
@pytest.mark.skipif(not _LANGGRAPH_AVAILABLE, reason="langgraph not installed")
@pytest.mark.parametrize("scenario_id", M4_SCENARIO_IDS[:5])
def test_langgraph_adapter_runs_scenario(scenario_id):
    ...
```

Does not assert scoring correctness (that's the mock-agent/scenario-test layer). Asserts only that the adapter produces a valid `RunArtifact` with populated trajectory and `status="completed"`.

### Example Agents

**`examples/langgraph_agent.py`** — Minimal real `create_react_agent` with 2-3 tools, runs against `langgraph[anthropic]` or `langgraph[openai]`. Runnable standalone or through the adapter.

**`examples/pydantic_ai_agent.py`** — Minimal real `pydantic_ai.Agent` with 2-3 tools, runs against `openai` or `anthropic` model. Runnable standalone or through the adapter.

---

## Documentation

### `docs/adapters/langgraph.md`
- Overview: what the adapter does
- Installation: `pip install evalforge[langgraph]`
- Agent contract: how to write `build_agent(payload)`
- Configuration: module, function, model, timeout
- Example: walk through `examples/langgraph_agent.py`
- Trajectory mapping: how LangGraph messages become EvalForge steps
- Error handling: what can go wrong and how to fix it

### `docs/adapters/pydantic-ai.md`
- Same structure for PydanticAI

---

## Out of Scope

- Custom LangGraph graphs (`StateGraph` directly — M6 only supports `create_react_agent`)
- LangGraph checkpointing / persistence
- PydanticAI result validators / dependency injection
- CLI-level adapter execution (M7)
- Structured output extraction beyond `result.data` (PydanticAI)
- Streaming invocation (all adapters are synchronous)

---

## Open Questions

1. Should `build_agent` receive the full payload or a filtered subset? → Design decision: receives full payload so user can access all scenario fields.
2. Should `model` override be a standard config key across both adapters? → Yes, both support it.
3. How to handle cost for LangGraph (no native token reporting)? → `cost=None` by default; user can provide cost in a response callback. Deferred to implementation.