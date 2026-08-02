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