# Scoring Guide

How scoring works in EvalForge — metric types, deterministic vs. LLM-as-judge, hybrid scoring, and how to write custom scorers.

**Quick start:** `from evalforge import evaluate` — the single-entry convenience import covers scoring, running, and reporting.

## Scoring Architecture

EvalForge scores agent runs against scenario expectations using a **hybrid** approach:

```
┌──────────────────────────────────────────────────────┐
│                  ScoringEngine                       │
│  ┌──────────────────┐  ┌──────────────────────┐      │
│  │ Deterministic     │  │ LLM-as-Judge         │      │
│  │ Scorers           │  │ Scorers              │      │
│  │ (fast, no-cost)   │→ │ (fallback when       │      │
│  │                   │  │  deterministic fails) │      │
│  └──────────────────┘  └──────────────────────┘      │
└──────────────────────────────────────────────────────┘
```

**Deterministic scorers** run first. They are fast, free, and produce repeatable results. If a deterministic scorer passes, the judge is skipped for that metric.

**LLM-as-judge scorers** run only when the deterministic gate fails (e.g., output correctness, task completion, synthesis quality). They produce a score (0.0–1.0) with a rationale.

**Hybrid scorers** (v0.2.0) combine both: the deterministic gate always runs,
even when no LLM judge is configured. If the judge is missing, the score
reflects the gate result and `judge_not_evaluated: true` is recorded. This
ensures safety guarantees are never silently skipped in offline mode.

## Metric Categories

| Category | Example Metrics | Source |
|---|---|---|
| **Tool** | tool_called, tool_correctness, argument_correctness, zero_disallowed | Deterministic |
| **Structure** | schema_validity, field_correctness | Deterministic |
| **Efficiency** | step_efficiency, cost_budget_adherence, retry_discipline, phantom_step_scorer | Deterministic |
| **Safety** | unsafe_action_avoidance, blast_radius_accuracy | Deterministic |
| **Grounding** | factual_consistency, source_citation, output_grounding, contradiction_detection | Deterministic |
| **Correctness** | output_correctness, task_completion | LLM-as-Judge |
| **Quality** | synthesis_quality, clarification_quality, refusal_quality, recovery_quality | LLM-as-Judge |
| **Groundedness** | hallucination_rate, evidence_grounding | LLM-as-Judge |

## Score Thresholds & Severity

Each metric has a threshold (0.0–1.0). Scores are classified:

| Score Range | Verdict | Meaning |
|---|---|---|
| >= threshold | PASS | Metric met |
| >= threshold * 0.7 | WARN | Close to failure, review needed |
| < threshold * 0.7 | FAIL | Metric not met |

**Evaluation hierarchy** (safety > correctness > efficiency):
- Safety violations → hard `FAIL` regardless of other metrics
- Correctness regressions → `WARN` by default
- Efficiency regressions → `WARN` by default

## Scoring Dimensions (v0.2.0)

Scores are reported across three independent dimensions, each gatable in CI:

| Dimension | Measures | Example failures |
|-----------|----------|------------------|
| `compatibility` | Adapter success, import health, no blank completions | Script crash, empty output |
| `safety` | Disallowed tools, budget adherence, sandbox violations | Called disallowed tool |
| `quality` | Trajectory correctness, answer quality, judge metrics | Wrong answer |

Use `--fail-on <dimension>` (or `all`) to gate a dimension in CI; exits non-zero
when the score falls below 0.8.

## Scoring Breakdown (v0.2.0)

Every scenario result includes a `scoring_breakdown` block:

- **`deterministic`** — per-check pass/fail for all deterministic scorers
- **`llm_judge`** — per-metric score and rationale for judge metrics
- **`divergences`** — where deterministic pass ≠ LLM pass, classified as:
  - `critical` — deterministic failed, LLM passed (agent used wrong tool to get right answer)
  - `warning` — deterministic passed, LLM failed (correct path, poor answer)

```bash
# Gate CI on critical divergences
evalforge run --pack my-pack.yaml --agent python:my_agent.py --ci --fail-on-divergence critical
```

## Phantom-Step Scorer (v0.2.0)

`phantom_step_scorer` is a deterministic trajectory scorer that flags tool calls
which don't advance agent state. It captures a state snapshot (steps executed,
artifacts touched, context hash) before and after each tool call:

- `state_after != state_before` → advancing step
- `state_after == state_before` → candidate phantom step

A warning is emitted when phantom steps exceed 30% of total steps. This makes
ineffective tool calls (e.g., re-reading the same artifact) detectable without
an LLM judge.

## Writing a Custom Scorer

Register a scorer with the `@register_scorer` decorator:

```python
from evalforge.scoring.registry import register_scorer
from evalforge.scoring.base import Scorer
from evalforge.models.artifact import RunArtifact
from evalforge.scoring.result import ScoreResult

@register_scorer
class MyCustomScorer(Scorer):
    name = "my_custom_metric"

    def score(self, artifact: RunArtifact, scenario: Any) -> ScoreResult:
        # Access the agent's output
        output = artifact.output.final or ""

        # Access trajectory steps
        tool_calls = [s for s in artifact.trajectory.steps if s.type == "tool_call"]

        # Return a score
        return ScoreResult(
            metric="my_custom_metric",
            score=0.85,
            threshold=0.8,
            passed=True,
            detail={"reason": "Custom check passed"},
        )
```

Custom scorers are auto-discovered via entry points or the registry.

## Judge Configuration

Configure judges in `evalforge.toml` or via CLI:

```toml
[judge]
provider = "openai"
model = "gpt-4o-mini"
```

```bash
evalforge run --judge openai:gpt-4o-mini --pack my-pack.yaml --agent python:my_agent.py
```

Judge evidence (prompts, verdicts, HTTP captures) is saved per scenario for auditability.

## Failure Taxonomy

EvalForge classifies failures to help you triage. For programmatic access, use `evalforge.analytics.FailureTaxonomy`:

| Failure Type | Detection | Example |
|---|---|---|
| **Tool misuse** | tool_correctness, argument_correctness | Called wrong tool or wrong args |
| **Tool underuse** | tool_called, step_efficiency | Agent didn't call tools when needed |
| **Tool overuse** | zero_disallowed, retry_discipline | Called forbidden tool or retry loop |
| **Output wrong** | output_correctness, task_completion | Factually incorrect answer |
| **Output malformed** | schema_validity, field_correctness | JSON didn't match schema |
| **Hallucination** | hallucination_rate, evidence_grounding | Fabricated facts not in context |
| **Safety breach** | unsafe_action_avoidance | Called production tool in test |
| **Budget exceeded** | cost_budget_adherence, step_efficiency | Too many steps or tokens |

## Determinism & Reproducibility

- **Deterministic scorers** always produce the same score for the same artifact.
- **Fixtures mode** replays tool responses from recorded data, producing identical runs on re-execution.
- **Baseline snapshots** capture scores at a point in time for regression comparison.
- **Cache** avoids redundant LLM judge calls within 24h TTL.

To maximize reproducibility:
1. Use fixtures mode in CI: `--fixtures`
2. Pin judge model and provider
3. Save baselines after each release
4. Compare in `snapshot` mode for strict CI gating
