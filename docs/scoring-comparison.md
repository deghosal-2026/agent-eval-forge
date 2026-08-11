# Deterministic vs. LLM-Based Scoring — Comparison

**Version:** 0.2.0
**Date:** 2026-08-10
**Source:** [JPS Integration Study](https://github.com/Judgment-Pack/judgment-pack-evaluator-experiments/tree/main/studies/013-agent-eval-forge-integration)

## Overview

The Judgment Pack Specification (JPS) integration study compared two scoring
approaches applied to the same set of 63 cases:
- **Deterministic evaluator**: rule-based judgment logic operating on structured
  data
- **LLM-based judge**: the same policy supplied as prose to a strong language
  model

The result was not simply "one beats the other." The two approaches fail
differently, and their failure classes barely overlap.

## Results

| Metric | Deterministic Evaluator | LLM Judge |
|---|---|---|
| Cases correct | 63/63 | 62/63 |
| Forbidden actions executed | 0 | 0 |
| Boundary failures | 0 (must leave ties unresolved) | 2 (resolved a tie incorrectly; corrupted structured routing data) |

### Two Boundary Failures

#### 1. Exact-Threshold Tie Resolution

The deterministic evaluator encounters an exact-threshold tie and must leave it
unresolved by design. The LLM judge resolved it — sometimes correctly by chance,
sometimes incorrectly. This is a **classification-boundary** issue: the model
"makes a call" where the spec demands ambiguity.

**When this matters:** policy enforcement at exact thresholds, rate-limit
decisions, cost-budget boundaries.

**Guidance:** Use deterministic scoring for threshold-based decisions. LLM
judges should not be asked to resolve ties that have no spec-defined resolution.

#### 2. Routing Destination Corruption

When the same routing information was carried as structured data, the
deterministic evaluator preserved it intact. When the LLM judge processed
equivalent information from prose, it repeatedly corrupted the routing
destination.

**When this matters:** any scoring path where the output feeds another system
(API endpoints, notification targets, database keys).

**Guidance:** Use deterministic scoring for structured output validation.
LLM judges are lossy with structured data — they can paraphrase, truncate,
or "fix" routing keys that were correct.

## Key Insight

> The two approaches fail differently and their failure classes barely overlap.
> Neither "deterministic beats model" nor "model beats deterministic" — they
> complement each other.

This is consistent with the [two-layer defense model](architecture.md): the
deterministic evaluator catches structural errors the LLM judge introduces, and
the LLM judge catches semantic errors the deterministic evaluator can't express
as rules.

## When to Use Each

### Deterministic Scoring

Use when:
- Exact correctness matters (routing keys, API endpoints, IDs)
- Threshold-based decisions require unambiguous pass/fail
- Offline/CI coverage is needed (no LLM judge available)
- The answer format is predictable (schema validation, field presence)
- Cost is a concern (deterministic scorers are free)

Examples: `tool_correctness`, `schema_valid`, `field_presence`, `step_count`,
`tool_sequence`, `phantom_step`

### LLM-Based Scoring

Use when:
- Semantic quality matters (synthesis, tone, reasoning)
- The expected answer can be expressed in natural language but not as a schema
- Boundary cases require human-like judgment
- You can tolerate occasional non-determinism in scoring

Examples: `task_completion`, `output_correctness`, `synthesis_quality`,
`clarification_quality`

### Hybrid Approach (Recommended)

EvalForge's recommended pattern:
1. Run deterministic gates first (cheap, reproducible, offline-safe)
2. Augment with LLM judge where semantic judgment adds value
3. Flag divergences between the two (critical if deterministic fails and LLM
   passes)

Configure with `--fail-on-divergence critical` in CI to catch cases where the
LLM judge passes a trajectory that deterministic checks flagged.

## Reproducibility

Full study, preregistration, hidden cases, artifacts, and detection matrix:
[JPS Integration Study](https://github.com/Judgment-Pack/judgment-pack-evaluator-experiments/tree/main/studies/013-agent-eval-forge-integration)
