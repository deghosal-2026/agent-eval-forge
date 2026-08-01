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