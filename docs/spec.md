# EvalForge Spec Notes

This file captures implementation-oriented details that are intentionally kept out of the PRD.

## Proposed Core Data Model

### Scenario Pack

A pack should include:

- scenario id
- title
- user goal
- starting state or context
- allowed / disallowed tools
- expected result or result schema
- evaluation dimensions
- tags
- difficulty
- domain metadata

### Run Artifact

A normalized run artifact should include:

- framework name and version
- agent version identifier
- model identifier
- scenario id
- start/end timestamps
- final output
- intermediate steps
- tool calls and arguments
- tool outputs
- token and cost metadata if available
- failure type if the run aborted

### Scores

At minimum:

- task completion
- output correctness
- tool correctness
- argument correctness
- step efficiency
- policy adherence
- latency
- cost

## Scoring Philosophy

EvalForge should be explicit that not all metrics are created the same way.

### Deterministic Metrics

Use deterministic checks whenever possible:

- schema validity
- exact field presence
- disallowed tool invocation
- budget overrun
- step count threshold
- timeout occurrence
- required tool called / not called

These are cheap, reproducible, and should be preferred for release gates.

### LLM-as-Judge Metrics

Use LLM judges where the behavior is semantic rather than exact:

- synthesis quality
- clarification quality
- conflict explanation quality
- hypothesis quality in debugging tasks
- plan quality
- decomposition quality in orchestrated tasks

These should return both a score and a rationale.

### Hybrid Metrics

Many agent scenarios need both:

- deterministic checks for hard boundaries
- semantic scoring for qualitative judgment

Example: a JSON extraction task can require deterministic schema validity while also using an LLM judge for semantic correctness of extracted values.

### Pass / Fail Philosophy

- **Hard fail metrics:** policy violation, unauthorized action, schema invalid output in schema-bound scenarios, disallowed tool use, explicit budget breach when configured as blocking.
- **Soft score metrics:** plan quality, synthesis quality, explanation quality, trajectory elegance.
- **Release gate default:** fail only on hard regressions or threshold breaches; surface soft-score deltas as warnings unless the pack explicitly promotes them to blocking.

### Comparison Model

Candidate versions should be compared against a baseline at three levels:

1. per scenario
2. per scenario family / tag
3. aggregate pack level

This avoids hiding important regressions inside average scores.

## v0.1 Launch Pack

The first official launch pack should be intentionally narrower than the full CUJ set.

### Launch Pack Scenarios

1. Single-Tool Factual Retrieval
2. Multi-Tool Retrieval Synthesis
3. Structured JSON Extraction
4. Tool Argument Precision
5. Disallowed Tool Refusal
6. Ambiguous User Request Clarification
7. Budget-Constrained Completion
8. Graceful Timeout / Partial-Failure Recovery

### Why These Eight

- They cover the core agent surface: correctness, tool use, policy, ambiguity, cost, and recovery.
- They are broadly applicable across frameworks.
- They create a credible v0.1 without requiring browser-only or deeply orchestrated infrastructure on day one.
- They provide enough diversity to catch real regressions rather than only exact-output drift.

## Adapter Targets For v0.1

### Adapter 1: LangGraph

- Prove EvalForge can score graph or trajectory-based workflows.
- Use LangGraph state and step structure where available.
- Demonstrate at least one tool-using multi-step scenario pack.

### Adapter 2: PydanticAI

- Prove EvalForge can evaluate typed output, tool usage, and Python-native workflows.
- Demonstrate simple adapter ergonomics for structured outputs and tool traces.

### Optional Next Framework

CrewAI is a strong follow-on candidate because of market share and multi-agent positioning, but should not be required for v0.1 if LangGraph and PydanticAI are solid.
