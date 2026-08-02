# Writing a Custom Adapter

This guide explains how to write a custom adapter for EvalForge when the built-in adapters (subprocess, python-import, HTTP, LangGraph, PydanticAI) don't fit your use case.

## Adapter Contract

Every adapter is a subclass of `evalforge.adapters.base.Adapter`:

```python
from typing import Any
from evalforge.adapters.base import Adapter
from evalforge.models.errors import AdapterError, AgentTimeoutError

class MyAdapter(Adapter):
    name = "my-adapter"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str | dict[str, Any]:
        # return a string (raw stdout) or a run envelope dict
        ...
```

### `_invoke()` Contract

| Aspect | Requirement |
|---|---|
| Input | `payload` — invocation dict with `input`, `context`, `allowed_tools`, `disallowed_tools`, `budget`. `config` — adapter-specific config from the agent block. |
| Return `str` | Parsed as raw stdout via `parse_agent_stdout()`. |
| Return `dict` | Treated as an `evalforge.run_envelope.v1` envelope (see below). |
| Timeout | Raise `AgentTimeoutError`. |
| Error | Raise `AdapterError` for any other failure. |

The base class `run()` method handles payload building, timing, error normalization, and artifact construction. You only implement `_invoke()`.

### Run Envelope Schema

When returning a `dict`, it must match:

```python
{
    "schema_version": "evalforge.run_envelope.v1",
    "status": "completed",           # or "error"
    "output": {"final": str, "structured": Any},
    "trajectory": {
        "steps": [
            {"type": "tool_call", "tool": str, "args": dict, "duration_ms": int},
            {"type": "tool_result", "tool": str, "result": Any, "duration_ms": int},
            {"type": "response", "content": str, "duration_ms": int},
        ]
    },
    "cost": {"input_tokens": int, "output_tokens": int, "total_tokens": int, "cost_usd": float},
    "error": None | str,
}
```

### Configuration Keys

Standard config keys the base class supports:

| Key | Default | Description |
|---|---|---|
| `run_id` | `"run-unknown"` | Run identifier |
| `strict_output` | `false` | If true, reject non-JSON agent output |
| `timeout_seconds` | 120 | Invocation timeout |

Add your own keys to `config` when constructing the adapter via the factory.

## Registration

Register your adapter in the factory so `create_adapter()` can find it:

```python
# src/evalforge/adapters/factory.py
from evalforge.adapters.my_adapter import MyAdapter

ADAPTERS = {
    "subprocess": SubprocessAdapter,
    "python": PythonImportAdapter,
    "http": HttpAdapter,
    "langgraph": LangGraphAdapter,
    "pydantic-ai": PydanticAIAdapter,
    "my-adapter": MyAdapter,  # <-- add this line
}
```

## Testing

Follow the existing test pattern:

```python
from evalforge.models.pack import Scenario
from evalforge.adapters.my_adapter import MyAdapter

def test_my_adapter():
    adapter = MyAdapter()
    scenario = Scenario(id="test", title="T", input="hello")
    config = {"run_id": "r1", "timeout_seconds": 10}
    artifact = adapter.run(scenario, config)
    assert artifact.status == "completed"
    assert artifact.output.final is not None
```

## Example: Minimal Echo Adapter

```python
class EchoAdapter(Adapter):
    name = "echo"

    def _invoke(self, payload, config):
        user_input = payload.get("input", "")
        return {
            "schema_version": "evalforge.run_envelope.v1",
            "status": "completed",
            "output": {"final": f"echo: {user_input}", "structured": None},
            "trajectory": {"steps": []},
            "cost": None,
            "error": None,
        }
```