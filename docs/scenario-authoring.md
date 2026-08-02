# Scenario Authoring Guide

This guide covers best practices for writing effective evaluation scenarios for EvalForge.

## Core Principles

### 1. Minimal Deterministic Prompts

Scenario inputs should be **minimal and unambiguous**. The goal is to test the agent's decision-making, not its ability to parse verbose instructions.

**Good:**
```yaml
input: "Look up the customer profile for customer_id=12345"
```

**Bad:**
```yaml
input: "I've been having trouble accessing my account. Can you help me find my customer profile? My ID might be 12345 but I'm not sure."
```

### 2. Tight Acceptance Checks

Use the most specific `expected` type that captures correctness:

| Expected Type | When to Use | Example |
|---------------|-------------|---------|
| `exact` | Literal string match | `value: "42"` |
| `schema` | JSON structure validation | `schema: {type: object, required: [name, email]}` |
| `tool_trace` | Ordered tool call sequence | `trace: [{tool: "customer_lookup", args: {id: "12345"}}]` |
| `tool_args` | Specific tool + arguments | `tool: "customer_lookup", args: {id: "12345"}` |
| `rubric` | Qualitative pass/fail criteria | `criteria: ["Output contains the customer's email"]` |

### 3. VCR Cassettes for E2E

For end-to-end tests that would normally call live APIs:

1. **Record** a cassette of the expected HTTP interactions:
```python
from evalforge.testing.vcr import LLMVCR

vcr = LLMVCR(cassette_dir="tests/integration/cassettes")
vcr.start_recording("my-scenario")
# ... run agent ...
vcr.stop_recording()
```

2. **Replay** in CI with no live API costs:
```python
cassette = vcr.replay("my-scenario")
response = vcr.get_llm_response(messages, model="gpt-4o-mini")
```

## Scenario Pack Structure

```yaml
pack:
  name: my-eval-pack
  version: "1.0.0"
  description: "Evaluation scenarios for customer service agent"
  trust: local
  infra_tags:
    - needs_api_key
    - network_access

scenarios:
  - id: lookup-01
    title: Single-Tool Customer Lookup
    input: "Look up customer 12345"
    allowed_tools:
      - name: customer_lookup
        description: "Fetch customer profile by ID"
    expected:
      type: tool_args
      tool: customer_lookup
      args:
        id: "12345"
    metrics:
      exact_match:
        threshold: 1.0
      tool_correctness:
        threshold: 1.0
    tags: [retrieval, single-tool]
    budget:
      max_steps: 3
      max_cost_usd: 0.01
```

## Metric Reference

### Deterministic Metrics (No LLM Judge)

| Metric | Description |
|--------|-------------|
| `exact_match` | Agent's final answer matches expected exactly |
| `schema_validity` | Output passes JSON schema validation |
| `field_correctness` | Required fields present in structured output |
| `tool_correctness` | Agent only called allowed tools |
| `tool_called` | Specific required tool was called |
| `tool_not_called` | Disallowed tool was NOT called |
| `argument_correctness` | Tool arguments match expected (exact or subset) |
| `step_efficiency` | Agent stayed within step budget |
| `cost_budget_adherence` | Agent stayed within cost budget |
| `zero_disallowed_actions` | No disallowed tools invoked (safety) |
| `unsafe_action_avoidance` | No unsafe-class tools invoked (safety) |
| `factual_consistency` | Output claims are backed by tool results |
| `source_citation` | Agent references valid tools/sources |
| `output_grounding` | Output is grounded in tool results |
| `contradiction_detection` | Output doesn't contradict tool results |
| `prompt_injection_resistance` | Agent resists prompt injection attacks |
| `data_exfiltration_prevention` | Agent prevents data exfiltration |
| `ssrf_prevention` | Agent prevents SSRF attacks |
| `sandbox_escape_resistance` | Agent resists sandbox escape attempts |

### LLM-as-Judge Metrics

| Metric | Description |
|--------|-------------|
| `task_completion` | Did the agent accomplish the goal? |
| `output_correctness` | Is the answer factually correct? |
| `synthesis_quality` | Quality of multi-source synthesis |
| `clarification_quality` | Quality of clarifying question |
| `refusal_quality` | Quality of safe refusal |
| `recovery_quality` | Quality of failure recovery |
| `hallucination_rate` | Degree of fabrication (6-category prompt) |
| `evidence_grounding` | Output grounded in evidence |

## Best Practices

### Tags

Use tags to group scenarios for analysis:
- **Domain**: `retrieval`, `synthesis`, `extraction`, `coding`
- **Complexity**: `single-tool`, `multi-tool`, `budget`
- **Safety**: `refusal`, `boundary`, `prompt-injection`, `ssrf`
- **Behavior**: `recovery`, `ambiguity`, `tool-avoidance`

### Budgets

Set realistic budgets to catch runaway agents:
```yaml
budget:
  max_steps: 10        # Hard limit on trajectory steps
  max_tokens: 5000     # Token budget
  max_cost_usd: 0.05   # Dollar cost ceiling
```

### Difficulty Levels

Tag scenario difficulty for progressive testing:
- `easy`: Single tool, straightforward input
- `medium`: Multiple tools, some ambiguity
- `hard`: Multi-step reasoning, edge cases, safety boundaries

### Infra Tags

Classify your agent's infrastructure needs:
```yaml
infra_tags:
  - needs_api_key      # Requires API key in env
  - network_access     # Makes HTTP calls
  - needs_db           # Accesses a database
  - filesystem_write   # Writes to filesystem
```

## Failure Taxonomy

When scenarios fail, EvalForge classifies them automatically:

| Category | Severity | Detection |
|----------|----------|-----------|
| `safety_violation` | critical | Unsafe action or boundary breach |
| `policy_violation` | critical | Disallowed tool was called |
| `agent_crash` | high | Agent process crashed |
| `timeout` | high | Agent exceeded time limit |
| `hallucination` | high | Fabricated facts not in context |
| `tool_error` | medium | Wrong tool selection |
| `argument_error` | medium | Wrong tool arguments |
| `schema_error` | medium | JSON didn't match schema |
| `budget_exceeded` | medium | Too many steps or tokens |
| `incorrect_output` | low | Factually incorrect answer |
| `incomplete_output` | low | Partial answer |
| `retry_exhausted` | low | Retry loop detected |
| `unknown` | low | Unclassified failure |

Use the analytics module for detailed analysis:
```python
from evalforge.analytics import FailureTaxonomy

report = FailureTaxonomy.analyze(run_score)
print(report.failure_breakdown)
print(report.recommendations)
```
