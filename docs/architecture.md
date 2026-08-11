# EvalForge — Architecture

**Version:** 0.2.0
**Date:** 2026-08-10

## Two-Layer Defense Model

EvalForge implements a two-layer defense architecture for agent regression
testing. Neither layer alone provides full coverage. Together they catch
different classes of failure with minimal overlap.

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Judgment Evaluator                            │
│  (agent's own test suite, deterministic evaluator)      │
│                                                         │
│  Catches: semantic/logic errors inside the agent's      │
│  decision-making. Judgment correctness, routing logic,  │
│  threshold comparisons, policy interpretation.          │
│                                                         │
│  Escapes: integration wiring, adapter misconfiguration, │
│  tool contract violations, artifact handling, exit      │
│  codes, scoring bugs, harness-level failures.           │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: EvalForge Integration Harness                 │
│  (scenario packs, trace scorers, comparison engine)     │
│                                                         │
│  Catches: integration errors (broken adapters, config   │
│  mistakes, tool wiring, I/O corruption) and enforces    │
│  structural/behavioral contracts (disallowed actions,   │
│  trajectories, exit codes, artifact integrity).         │
│                                                         │
│  Escapes: judgment-logic errors that produce well-      │
│  formed but semantically wrong outputs.                 │
└─────────────────────────────────────────────────────────┘
```

### Layer 1: Judgment Evaluator

The judgment evaluator lives inside or alongside the agent under test. It
validates the agent's reasoning, policy adherence, and decision quality. This
layer is tested by its own unit and integration tests.

What Layer 1 catches:
- Incorrect judgment logic
- Policy misinterpretation
- Threshold comparison errors
- Reasoning flaws in the agent's decision path

What Layer 1 cannot catch:
- Adapter misconfiguration (wrong module path, broken import)
- Tool wiring errors (agent calls live tools in supposedly-deterministic mode)
- Exit code contract violations (safety violations exit 0)
- Artifact handling bugs (status not consulted, crashed agents score as passing)
- Harness-level regressions (snapshot comparison broken, baselines incomplete)

### Layer 2: EvalForge Integration Harness

EvalForge sits outside the agent and observes its behavior through the adapter
contract. It scores both the outcome and the trajectory using deterministic
scorers, optional LLM judges, and comparison against baselines.

Key enforcement mechanisms:
- **Trace scorers** (`zero_disallowed_actions`, `tool_correctness`,
  `tool_called`, `step_efficiency`, `phantom_step`): deterministic checks on
  the agent's execution trace
- **Comparison engine**: detects regressions between baselines and candidates
  across score deltas, status transitions, adapter changes, and model changes
- **Exit codes**: 0 (pass), 1 (failure), 3 (judge error), 4 (safety violation),
  5 (critical divergence)
- **Artifact integrity**: scoring short-circuits on non-completed artifacts,
  scorer exceptions are surfaced as failures
- **Tool contracts**: `ToolStub` interception for deterministic/replay mode,
  disallowed-tool enforcement

## Empirical Validation: JPS Integration Study

The two-layer model was empirically validated by the Judgment Pack
Specification (JPS) integration study against EvalForge at commit `8925cac`.

### Study Design

- **20 failures injected**: some inside judgment logic, others in the
  integration layer around it
- **All 20 detection predictions held**: each failure was tagged in advance
  with which layer was expected to catch it
- **4 hidden adversarial cases** written by an independent reviewer, one
  intentionally designed to escape the judgment layer

### Results

| Failure Class | Layer 1 Caught? | Layer 2 Caught? |
|---|---|---|
| Judgment-semantic errors | Yes | No |
| Integration wiring errors | No | Yes |
| Protected-action violations | No | Yes (`zero_disallowed_actions`) |
| Adversarial case (escapes Layer 1) | No | Yes (`argument_correctness`) |

The adversarial case confirmed the model: a case designed to pass every
judgment-layer test was caught downstream by EvalForge's trace scorers.

### Conclusion

> "An external regression harness can detect integration mistakes that a
> perfectly correct judgment evaluator cannot see."

This is the fundamental design principle: **Layer 1 and Layer 2 catch
different classes of failure, and their failure classes barely overlap.**

Full study artifacts: [JPS Integration Study](https://github.com/Judgment-Pack/judgment-pack-evaluator-experiments/tree/main/studies/013-agent-eval-forge-integration)

## Failure-Class Coverage Matrix

| Failure Mode | Layer 1 | Layer 2 | Example |
|---|---|---|---|
| Wrong routing decision | Catches | May miss | Agent routes to wrong handler but produces valid output |
| Threshold tie resolved | Catches | Misses | Deterministic evaluator must leave unresolved; model resolves incorrectly |
| Broken module import | Misses | Catches | `python:my_module:run` → `ModuleNotFoundError` |
| Crashed agent scores as passing | Misses | Catches | `artifact.status: "error"` not consulted by scoring |
| Disallowed tool executed | Misses | Catches | `zero_disallowed_actions` blocks it |
| Tool stub not wired | Misses | Catches | Agent calls live tool in deterministic mode |
| Exit code 0 on safety violation | Misses | Catches | CI gate passes everything silently |
| Baseline comparison broken | Misses | Catches | Score drops invisible to comparison engine |
| Rubric criteria ignored | May miss | Catches | Hand-written criteria never reach judge prompt |
| Config/environment mismatch | Misses | Catches | Adapter digest detects adapter/runner change |

## Recommended Configuration

To set up a two-layer defense:

1. **Layer 1** — Your agent's own test suite validates judgment logic. This
   lives in your agent repository and runs before EvalForge.

2. **Layer 2** — EvalForge runs in CI as a post-merge or pre-release gate:

   ```bash
   # Run all scenarios
   evalforge run --pack scenarios/core-launch.yaml --agent python:my_agent:run

   # Compare against baseline (detects regressions, adapter changes, model changes)
   evalforge compare --baseline baselines/prod.json --candidate scores.json

   # Fail on any failure dimension
   evalforge run --pack scenarios/core-launch.yaml --fail-on compatibility,safety,quality
   ```

3. **Adversarial cases** — Add scenarios targeting known blind spots (see
   [Adversarial Scenarios](scenario-authoring.md#adversarial-scenarios)).

## Design Principles

1. **Separate observation from execution.** EvalForge observes the agent through
   the adapter contract. It never modifies agent behavior during scoring.

2. **Catch what the judgment layer misses.** Every bug found in the JPS study
   (#269-#274) was invisible to the judgment layer's own tests. EvalForge
   exists to catch these integration-class failures.

3. **Fail loudly.** Exit codes are non-zero on safety violations, judge errors,
   and critical divergences. CI gates that pass everything silently are the
   most consequential failure mode.

4. **Deterministic gates first, LLM judges second.** Every safeguard that can
   be implemented deterministically should be, so offline users and CI
   pipelines get coverage without requiring an LLM judge.

5. **Layer, don't replace.** EvalForge is the complement to a judgment
   evaluator, not its replacement.

## Companion Bug Reports

The following EvalForge issues (#269-#274) were discovered during the JPS
study and are concrete examples of Layer 2 catching what Layer 1 misses:

| Issue | What Layer 2 Caught |
|---|---|
| [#269](https://github.com/deghosal-2026/agent-eval-forge/issues/269) | Exit codes never non-zero; CI gates pass everything |
| [#270](https://github.com/deghosal-2026/agent-eval-forge/issues/270) | Crashed agents score as passing; `artifact.status` never consulted |
| [#271](https://github.com/deghosal-2026/agent-eval-forge/issues/271) | Regression detection blind to score drops; snapshots broken |
| [#272](https://github.com/deghosal-2026/agent-eval-forge/issues/272) | ToolStub honour-system; no interception of tool calls |
| [#273](https://github.com/deghosal-2026/agent-eval-forge/issues/273) | Rubric criteria dead text; judges never see trajectories |
| [#274](https://github.com/deghosal-2026/agent-eval-forge/issues/274) | CLI broken: agent spec, init scaffold, metric alias |
