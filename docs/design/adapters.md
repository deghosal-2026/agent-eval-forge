# Framework Adapters — Design

Covers the LangGraph and PydanticAI adapter architecture, user contract, trajectory extraction, and test strategy.

## Overview

Add adapters for popular agent frameworks: LangGraph (prebuilt `create_react_agent`)
and PydanticAI. Unlike the existing `PythonImportAdapter` (which requires the user
to manually build an EvalForge run envelope), these adapters auto-extract trajectory,
tool calls, and output from the framework's native result structures. The user writes
natural framework code; the adapter handles the EvalForge contract.

## Files

| File | Purpose |
|---|---|---|
| `src/evalforge/adapters/langgraph.py` | `LangGraphAdapter` class |
| `src/evalforge/adapters/pydantic_ai.py` | `PydanticAIAdapter` class |
| `src/evalforge/adapters/isolated.py` | `IsolatedAdapter` — sandboxed subprocess wrapper |
| `src/evalforge/adapters/worker.py` | `WorkerAdapter` — pooled execution backend |
| `src/evalforge/adapters/factory.py` | Register all in `ADAPTERS` dict |
| `tests/test_adapters_langgraph.py` | Unit tests |
| `tests/test_adapters_pydantic_ai.py` | Unit tests |
| `tests/fixtures/langgraph_agent.py` | Test stub agent (no real LLM) |
| `tests/fixtures/pydantic_ai_agent.py` | Test stub agent (no real LLM) |
| `examples/langgraph_agent.py` | Runnable example agent |
| `examples/pydantic_ai_agent.py` | Runnable example agent |
| `docs/adapters/langgraph.md` | Adapter usage documentation |
| `docs/adapters/pydantic-ai.md` | Adapter usage documentation |

## Adapter Registration

```python
ADAPTERS = {
    "subprocess": SubprocessAdapter,
    "python": PythonImportAdapter,
    "http": HttpAdapter,
    "langgraph": LangGraphAdapter,
    "pydantic-ai": PydanticAIAdapter,
    "isolated": IsolatedAdapter,
    "worker": WorkerAdapter,
}
```

## User Contract

The user's Python module must export a `build_agent` function:

```python
# examples/langgraph_agent.py
from langgraph.prebuilt import create_react_agent
from langgraph.graph import CompiledGraph

def build_agent(payload: dict) -> CompiledGraph:
    """Build a prebuilt ReAct agent from the scenario payload."""
    return create_react_agent(model, tools=tools)
```

### Module Resolution

Same pattern as `PythonImportAdapter`: config specifies `module` (dotted Python
path) and `function` (default `"build_agent"`). The adapter calls
`importlib.import_module(module)` then `getattr(mod, function)(payload)`.

### Config Keys

| Key | Required | Default | Description |
|---|---|---|---|
| `module` | Yes | — | Dotted Python module path |
| `function` | No | `"build_agent"` | Function name in that module |
| `model` | No | None | Optional model override |
| `timeout_seconds` | No | 120 | Agent invocation timeout |
| `run_id` | No | `"run-unknown"` | Run identifier |

## LangGraph Adapter

### Invocation

```python
user_input = payload["input"]
initial_state = {"messages": [{"role": "user", "content": user_input}]}
result = agent.invoke(initial_state)
```

### Trajectory Extraction

Walk `result["messages"]`:
1. **`AIMessage` with `tool_calls`** → `tool_call` step per call
2. **`ToolMessage`** → `tool_result` step (matched by `tool_call_id`)
3. **Final `AIMessage` without `tool_calls`** → `response` step

### Error Mapping

| LangGraph Error | Adapter Error |
|---|---|
| Import error | `AdapterError("install langgraph extra")` |
| Invocation error | `AdapterError` |
| Timeout | `AgentTimeoutError` |

## PydanticAI Adapter

### Invocation

```python
user_input = payload["input"]
result = agent.run_sync(user_input)
```

### Trajectory Extraction

Walk `result.all_messages()`:
1. **`ToolCallPart` / `ToolRunPart`** → `tool_call` steps
2. **`ToolReturnPart` / `RetryToolPart`** → `tool_result` steps
3. **Final assistant message content** → `response` step

### Output Extraction

- `final` = `str(result.data)` (the typed output converted to string)
- `structured` = `result.data` (the raw typed output)

### Cost Extraction

PydanticAI `result.usage()` provides token counts. If available, populate the
`cost` field. Otherwise `cost=None`.

## Error Handling

### Common

| Scenario | Behavior |
|---|---|
| `build_agent` returns wrong type | `AdapterError` |
| Agent returns unexpected shape | `AdapterError` (with diagnostic detail) |
| Module not found | `AdapterError` with install guidance |
| Invocation exceeds timeout | `AdapterError` → `AgentTimeoutError` |

### LangGraph-Specific

| Scenario | Behavior |
|---|---|
| `result["messages"]` missing | `AdapterError("missing messages key")` |
| Unknown message type | Skipped (not added to trajectory) |
| Tool call with missing name | Skipped |

### PydanticAI-Specific

| Scenario | Behavior |
|---|---|
| Unknown part kinds | Skipped |
| `result.data` has no `__str__` | Fallback to repr |

## Testing

### Unit Tests (no real LLM)

Each adapter test creates a `Scenario` with a known tool list, uses a minimal
test fixture agent (no real model), and asserts on the returned `RunArtifact`:
1. **Envelope path** — well-formed structure → artifact has correct trajectory
2. **Error path** — `build_agent` raises → status=error
3. **Timeout path** — agent times out → status=timeout
4. **Trajectory extraction** — agent with tool calls → correct steps
5. **Message type handling** — unexpected types skipped gracefully

### Integration Tests

Parametrized test that runs launch scenarios 1-5 through each adapter, asserting
the adapter produces a valid `RunArtifact` with populated trajectory and
`status="completed"`.

## Out of Scope

- Custom LangGraph graphs (only `create_react_agent` supported)
- LangGraph checkpointing / persistence
- PydanticAI result validators / dependency injection
- CLI-level adapter execution (M7)
- Structured output extraction beyond `result.data`
- Streaming invocation (all adapters are synchronous)