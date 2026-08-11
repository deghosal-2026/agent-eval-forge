# Scenario Authoring Guide

How to write scenario packs for EvalForge — pack structure, scenario anatomy, metric selection, and best practices.

## Pack Structure

A scenario pack is a YAML file that groups related test scenarios:

```yaml
pack:
  name: "my-pack"
  version: "1.0.0"
  description: "Custom validation pack"
  min_evalforge: "0.2.0"

scenarios:
  - id: "my-scenario-01"
    title: "Policy lookup"
    goal: "Retrieve policy details with a single tool call"
    input: "What is the return policy?"
    allowed_tools:
      - name: "policy_lookup"
    disallowed_tools: []
    expected:
      type: exact
      value: "30-day return window"
    metrics:
      task_completion: {threshold: 1.0}
      tool_correctness: {threshold: 1.0}
    tags: [retrieval, single-tool]
    difficulty: easy
    budget: {max_steps: 3, max_tokens: 300}
```

## Scenario Fields

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Unique ID within the pack (alphanumeric + hyphens/underscores) |
| `title` | Yes | Human-readable title |
| `goal` | Yes | What the agent should accomplish |
| `input` | Yes | User message sent to the agent |
| `allowed_tools` | No | Tools the agent may use (name, description, parameters) |
| `disallowed_tools` | No | Tools the agent must NOT use |
| `expected` | No | What constitutes a correct answer |
| `metrics` | No | Scoring metrics and thresholds |
| `tags` | No | Category tags for filtering |
| `difficulty` | No | easy / medium / hard |
| `budget` | No | Resource limits (max_steps, max_tokens) |

## Expected Answer Types

| Type | Description | Example |
|---|---|---|
| `exact` | Exact string match | `value: "Tokyo"` |
| `schema` | JSON Schema validation | `schema: {name: str, age: int}` |
| `rubric` | Qualitative criteria for judge | `criteria: ["Must mention city", "Must cite source"]` |
| `tool_trace` | Tool call sequence check | `trace: [{tool: search, args_match: subset}]` |

## Metric Reference

| Metric | Category | Source | When to Use |
|---|---|---|---|
| `tool_called` | Tool | Deterministic | Agent must call at least one tool |
| `tool_correctness` | Tool | Deterministic | Agent called the right tools |
| `argument_correctness` | Tool | Deterministic | Agent passed correct arguments |
| `zero_disallowed` | Tool | Deterministic | Agent never touched forbidden tools |
| `schema_validity` | Structure | Deterministic | Output valid against JSON schema |
| `field_correctness` | Structure | Deterministic | Required fields all present |
| `step_efficiency` | Efficiency | Deterministic | Steps within budget |
| `retry_discipline` | Efficiency | Deterministic | No retry loops |
| `cost_budget_adherence` | Efficiency | Deterministic | Cost within budget |
| `factual_consistency` | Grounding | Deterministic | Output claims internally consistent |
| `source_citation` | Grounding | Deterministic | Sources cited when available |
| `output_grounding` | Grounding | Deterministic | Claims traceable to trajectory |
| `contradiction_detection` | Grounding | Deterministic | No self-contradiction in output |
| `task_completion` | Correctness | Judge | Did agent accomplish the goal? |
| `output_correctness` | Correctness | Judge | Is the answer factually correct? |
| `synthesis_quality` | Quality | Judge | Multi-source synthesis quality |
| `clarification_quality` | Quality | Judge | Quality of clarifying question |
| `refusal_quality` | Quality | Judge | Quality of safe refusal |
| `recovery_quality` | Quality | Judge | Quality of failure recovery |
| `hallucination_rate` | Quality | Judge | Fabrication rate |
| `evidence_grounding` | Quality | Judge | Claims supported by evidence |

## Best Practices

### 1. Start Simple
Begin with deterministic metrics (tool_correctness, schema_validity). Add judge metrics only when needed.

### 2. Keep Prompts Focused
Each scenario should test ONE thing. Don't combine tool precision + refusal + structured output in one scenario.

### 3. Use Fixtures for Determinism
Fixture data decouples scenarios from live services. Tool responses are recorded and replayed for identical results.

```yaml
fixtures:
  - name: "policy_lookup"
    response: {"policy": "30-day return window"}
```

### 4. Tag Strategically
Use tags to group scenarios for parallel runs, CI filtering, and reporting:

```yaml
tags: [retrieval, single-tool, regression]
```

### 5. Budget Realistically
Set budgets high enough for the agent to complete the task but low enough to catch runaway behavior:

```yaml
budget: {max_steps: 5, max_tokens: 500}
```

### 6. Disallowed Tools for Safety
Use `disallowed_tools` to verify the agent respects boundaries:

```yaml
disallowed_tools:
  - name: "deploy_production"
```

### 7. Validate Before Running
```bash
evalforge validate --pack my-pack.yaml --strict
```

## Running Scenarios

```bash
# Run all scenarios in a pack
evalforge run --pack my-pack.yaml --agent python:my_agent.py

# Run filtered by tag
evalforge run --pack my-pack.yaml --agent python:my_agent.py --tags retrieval

# Run with fixtures (deterministic, no live services)
evalforge run --pack my-pack.yaml --agent python:my_agent.py --fixtures

# Run and save a baseline
evalforge run --pack my-pack.yaml --agent python:my_agent.py --baseline v1.0

# Compare against a baseline
evalforge compare --candidate .evalforge/runs/latest --baseline v1.0
```
