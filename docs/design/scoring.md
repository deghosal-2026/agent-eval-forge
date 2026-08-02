# Scoring Engine — Design

Covers the scoring architecture: deterministic scorers, LLM-as-judge, hybrid scoring, evaluation hierarchy, and exit codes.

## Goal

Score run artifacts against scenario `expected`/`metrics` using deterministic
scorers, LLM-as-judge scorers, and hybrid scoring, then aggregate results per
scenario and per run with the safety > correctness > efficiency hierarchy and
CI exit-code resolution.

## Metric Vocabulary

Launch-pack metric names are the canonical surface. The spec's scoring catalog
names (`exact_match`, `schema_valid`, `field_presence`, `tool_called`,
`tool_not_called`, `tool_args_match`, `step_count`, `token_count`, `cost_budget`,
`timeout`, `tool_sequence`) are registered as aliases where they map to a
launch-pack equivalent. Catalog scorers with no launch-pack counterpart
(`tool_sequence`, `token_count`, `timeout`, `plan_quality`,
`conflict_explanation`, `hallucination_check`) are registered but marked
not-in-launch-pack and deferred unless trivial.

### Metric Classification

**Deterministic (12):**

| Metric | Checks | Source |
|--------|--------|--------|
| `tool_correctness` | trajectory tool calls use allowed tools / disallowed tools refused | artifact.trajectory, scenario.allowed_tools/disallowed_tools |
| `zero_disallowed_actions` | no disallowed tool called | artifact.trajectory, scenario.disallowed_tools |
| `unsafe_action_avoidance` | no unsafe/approval-boundary action taken | artifact.trajectory, scenario context |
| `schema_validity` | `output.final`/`structured` validates against `expected.schema` | artifact.output, scenario.expected |
| `field_correctness` | required fields present in output | artifact.output, scenario.expected |
| `argument_correctness` | tool call args match expected (exact/subset/superset) | artifact.trajectory, scenario.expected |
| `step_efficiency` | steps within `budget.max_steps` | artifact.trajectory, scenario.budget |
| `cost_budget_adherence` | cost within `budget.max_cost_usd` | artifact.cost, scenario.budget |
| `factual_consistency` | output claims are consistent with each other | artifact.output, scenario.context |
| `source_citation` | output cites sources when available | artifact.output, artifact.trajectory |
| `output_grounding` | output claims traceable to trajectory evidence | artifact.output, artifact.trajectory |
| `contradiction_detection` | output does not contradict itself or trajectory | artifact.output, artifact.trajectory |

**Judge (11):**

| Metric | Evaluates |
|--------|-----------|
| `task_completion` | Did the agent accomplish the goal? |
| `output_correctness` | Is the answer factually correct? |
| `synthesis_quality` | Quality of multi-source synthesis |
| `clarification_quality` | Quality of clarifying question |
| `refusal_quality` | Quality of safe refusal |
| `recovery_quality` | Quality of failure recovery |
| `blast_radius_accuracy` | Accuracy of change-impact assessment |
| `verification_quality` | Quality of verification steps |
| `hypothesis_quality` | Quality of debugging hypotheses |
| `evidence_grounding` | Claims grounded in available evidence |
| `hallucination_rate` | Degree of fabrication / ungrounded claims |

**Hybrid (2):** deterministic gate first; skip judge on clean pass/fail; judge
fallback when the gate is inconclusive.

| Metric | Deterministic gate | Judge fallback |
|--------|--------------------|----------------|
| `policy_adherence` | trajectory tool calls vs allowed/disallowed/approval-boundary rules | semantic policy-respect assessment |
| `retry_discipline` | detect repeated identical tool calls / retry loops | semantic recovery-behavior assessment |

## Architecture

```
src/evalforge/scoring/
├── base.py            # Scorer ABC
├── result.py          # ScoreResult, ScenarioScore, RunScore, JudgeVerdict
├── registry.py        # @register_scorer + SCORERS + entry-point discovery
├── engine.py          # ScoringEngine
├── deterministic/
│   ├── tools.py       # tool_correctness, zero_disallowed_actions, unsafe_action_avoidance
│   ├── output.py      # schema_validity, field_correctness
│   ├── args.py        # argument_correctness
│   ├── budget.py      # step_efficiency, cost_budget_adherence
│   ├── grounding.py   # factual_consistency, source_citation, output_grounding, contradiction_detection
│   └── gates.py       # policy_adherence gate, retry_discipline gate
├── judge/
│   ├── client.py      # JudgeClient ABC
│   ├── openai.py      # OpenAI-compatible client
│   ├── anthropic.py   # Anthropic client
│   ├── ollama.py      # Ollama client
│   ├── mock.py        # MockJudge
│   └── scorers.py     # 11 judge scorers
└── hybrid.py          # HybridScorer wrapper
```

### Scorer ABC (`scoring/base.py`)

```python
class Scorer(ABC):
    name: str            # metric name this scorer implements
    kind: str            # "deterministic" | "judge"
    def score(self, artifact: RunArtifact, scenario: Scenario,
              metric_config: dict) -> ScoreResult: ...
```

### Result types (`scoring/result.py`)

- `ScoreResult` — metric, score (0–1), threshold, `passed: bool`, `blocking: bool`,
  `error: str | None`, `detail: dict`, `source: "deterministic"|"judge"`.
- `ScenarioScore` — scenario_id, `results: dict[str, ScoreResult]`, overall status
  (`passed`/`warn`/`failed`), `safety_violations: list[str]`.
- `RunScore` — per-scenario `ScenarioScore`s, aggregates (passed/warned/failed
  counts), resolved `exit_code: int`.
- `JudgeVerdict` — `score: float` (clamped 0–1), `rationale: str`.

### Registry (`scoring/registry.py`)

- `@register_scorer(cls)` decorator → inserts into `SCORERS[name]`.
- Duplicate-name registration raises `ConfigError`.
- `discover_entry_points()` loads externally registered scorers (spec
  §"Custom Scorer Registration"); no-op when no plugins installed.
- `ALIASES` maps spec catalog names to launch-pack names where they exist.

### Deterministic scorers (`scoring/deterministic/`)

Implement the 12 deterministic metrics. The 4 grounding scorers (`grounding.py`) check factual consistency, source citation, output-to-trajectory grounding, and contradiction detection. All scorers read only from
`artifact.trajectory`, `artifact.output`, `artifact.cost`, `scenario.budget`,
`scenario.allowed_tools`, `scenario.disallowed_tools`, `scenario.expected`.

### Judge client abstraction (`scoring/judge/`)

```python
class JudgeClient(ABC):
    name: str
    def judge(self, prompt: str, *, max_tokens: int = 512,
              temperature: float = 0.0) -> JudgeVerdict: ...
```

- `OpenAIClient` — OpenAI-compatible chat completions (also serves local
  OpenAI-protocol servers).
- `AnthropicClient` — Messages API.
- `OllamaClient` — local `/api/chat`.
- `MockJudge` — returns a configurable verdict; used by tests and offline runs.
- Verdicts require `{"score": float, "rationale": str}`; score clamped to [0,1];
  malformed verdicts raise `JudgeError`.

### Judge scorers (`scoring/judge/scorers.py`)

Each judge scorer builds a prompt from `scenario.goal`/`input`/`expected` and
`artifact.output`/`artifact.trajectory`, calls the configured `JudgeClient`, and
maps the verdict into a `ScoreResult`. Uses `temperature=0.0` for determinism.

### Hybrid scoring (`scoring/hybrid.py`)

`HybridScorer` wraps a deterministic gate scorer and a judge scorer:

1. Run the deterministic gate against `metric_config.threshold`.
2. Clean pass → return deterministic result (judge skipped).
3. Clean fail → return deterministic result (judge skipped).
4. Inconclusive (gate cannot determine) → run judge scorer, return its result.

### ScoringEngine (`scoring/engine.py`)

```python
class ScoringEngine:
    def score_run(self, pack: ScenarioPack, artifacts: list[RunArtifact],
                  judge: JudgeClient | None = None) -> RunScore: ...
```

- Validates all metric names in the pack resolve in `SCORERS` first
  (unknown metric → `ConfigError`).
- Per scenario: for each `metrics` entry, resolve scorer (honoring `kind` override
  in the metric config), run it, build `ScoreResult`.
- Per metric config: `threshold` drives `passed`; `blocking: true` promotes a
  correctness/efficiency metric to fail the run.
- Per scenario: aggregate into `ScenarioScore` with the hierarchy
  (safety > correctness > efficiency).
- Per run: aggregate into `RunScore` + resolve exit code.
- Optionally writes `.evalforge/runs/<run_id>/scores.json`.

## Evaluation Hierarchy

Safety > correctness > efficiency.

- **Safety class** (hard fail, exit 4): `zero_disallowed_actions`,
  `unsafe_action_avoidance`, `policy_adherence`. A failed safety metric marks the
  scenario failed and blocks the run regardless of other metrics.
- **Correctness class** (fail, exit 1): `tool_correctness`, `schema_validity`,
  `field_correctness`, `argument_correctness`, `task_completion`,
  `output_correctness`, `synthesis_quality`, `clarification_quality`,
  `refusal_quality`, `recovery_quality`, `blast_radius_accuracy`,
  `verification_quality`, `hypothesis_quality`, `evidence_grounding`.
- **Efficiency class** (warn, informational): `step_efficiency`,
  `cost_budget_adherence`, `retry_discipline`. Fails do not fail the run unless
  promoted with `blocking: true`.

## Exit Codes

Per spec:

| Code | Meaning |
|------|---------|
| 0 | All scenarios passed |
| 1 | One or more scenarios failed (regression or threshold breach) |
| 2 | Configuration error (unknown metric, invalid scoring config) |
| 3 | Infrastructure error (judge unavailable/failure) |
| 4 | Safety boundary violation detected |

Resolution order: safety failure (4) > config error (2) > judge infra (3) >
scenario failure (1) > pass (0).

## Error Handling

- Unknown metric name → `ConfigError` at engine start (exit 2), before any scoring.
- A scorer that raises unexpectedly → catch, emit `ScoreResult(error=...)`,
  scenario marked failed (exit 1); the run continues (a scenario failure never
  aborts the run — same principle as M1).
- Judge call failure/timeout/malformed verdict → `JudgeError` → that metric
  records `error`; if any scenario requires judge, run resolves to exit 3
  (unless safety failure → 4). Judge per-call timeout configurable.
- Judge verdict parsing: require `{"score": float, "rationale": str}`; clamp
  score to [0,1]; malformed → judge error.

## Scope Boundaries

- Scoring results are returned as objects; optionally written to
  `.evalforge/runs/<run_id>/scores.json` for M3.
- Spec catalog scorers with no launch-pack counterpart are deferred unless
  trivial.
- The `evalforge.analytics` module provides `FailureTaxonomy` and related utilities for programmatic post-scoring analysis.