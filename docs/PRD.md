# PRD: Agent Eval Forge

**Status:** Approved  
**Version:** 1.0  
**Date:** 2026-07-28  
**Author:** Debashish Ghosal

## Problem Statement

Teams building AI agents keep changing prompts, models, tools, memory, and orchestration logic, but most still evaluate progress by eyeballing a handful of examples. That works for demos. It fails for production.

Agent systems are harder to evaluate than plain LLM calls because:

- the final answer is not the only thing that matters
- the path taken matters
- tool selection and tool arguments matter
- cost and latency matter
- policy and safety behavior matter
- regressions often appear in specific scenario families, not in averages

The result is release decisions made on anecdotes, cherry-picked demos, and optimism instead of evidence.

**Agent Eval Forge exists to make agent improvement measurable, repeatable, and comparable across versions.**

## Value Proposition

Agent Eval Forge is a framework-agnostic evaluation harness for tool-using agents. It lets teams define scenario packs, run agents consistently, score outcomes and trajectories, and detect regressions before changes hit production.

The product is intentionally **Python-first** in implementation, while remaining **framework-agnostic** in positioning and adapter design.

> *"Did the agent actually get better, or did it just change?"*

## Product DNA

These are the product truths that drive every decision in EvalForge. They are what makes this product different from a generic eval framework.

### Primary Promise

**Stop unsafe agent changes from shipping.**

EvalForge exists to catch regressions that matter before they reach production. The primary job is release gating for tool-using agents with real side effects, policy boundaries, and data-boundary risk.

### Who It's For (In Order)

1. **Solo OSS builders** shipping tool-using agents who need release confidence
2. **Small teams** with internal agents who need repeatable baselines
3. **Platform teams** supporting many agent repos who need shared governance

### Decisions It Helps Make

- Can I safely merge this prompt, model, or tool change?
- Did this version regress?
- Which design or framework performs better?
- Which scenario families are still weak?

### Day-One Win

Catch one regression before merge. That is the smallest meaningful adoption outcome.

### Product Identity

EvalForge is a **release-discipline product** first. Learning and comparison are secondary.

### Product Posture

**Strong default rubrics out of the box.** Teams get credible pass/fail behavior immediately. Everything is overridable, but defaults matter.

### Mental Model

**`pytest for agents`** is the lead identity. It tells users what the product feels like. `playwright for agent scenarios` supports as a secondary analogy for scenario authoring, but the lead is testing-and-gating.

### Evaluation Hierarchy

1. **Safety** — data boundaries, disallowed tools, unauthorized actions
2. **Correctness** — answer quality, accuracy, completeness
3. **Efficiency** — cost, tokens, step count, latency

Safety regressions fail by default. Correctness and efficiency regressions warn by default unless promoted by the scenario pack.

### What Safety Means Here

The most important failure EvalForge must catch is an agent crossing a data boundary it should never touch. This means:

- unauthorized data access
- retrieval from forbidden sources
- context leakage across tasks, tenants, or users
- use of tools that expose sensitive information

Safety-boundary violation handling is **configurable per scenario pack, but defaults to blocking.**

### Primary Evidence

**Score deltas** are the primary trust artifact when EvalForge claims a regression. Traces and scenario-level diffs support the score.

### Primary Moat

**Strong default rubrics.** The built-in scoring, especially around safety behavior, is what makes EvalForge valuable out of the box.

### Baselines

EvalForge prefers **explicit golden baselines** — an intentionally accepted known-good version. Comparisons are not against "last run wins" or "whatever is on main."

### Trace Posture

EvalForge works with minimal artifacts and gets stronger with richer traces. Rich instrumentation is a multiplier, not a prerequisite.

### How You Adopt

1. One agent
2. One scenario pack
3. One explicit golden baseline

That is the minimal adoption path. Teams should not need mature agent infrastructure to get started.

### Where You Run

**Local-first** for developer decisions. **CI-second** for enforcement. The developer catches issues before merge. CI enforces as the practice matures.

### Framework-Agnostic Means

**Adapter-based support for multiple runtimes.** EvalForge ships tested adapters for OSS frameworks. It does not claim compatibility it cannot prove.

### Competitive Wedge

**Better release gating for agent changes.** Not a generic LLM eval framework. Not a benchmark leaderboard. Not a hosted observability platform. EvalForge is built for one job: deciding whether an agent change is safe to ship.

### Pack Philosophy

**Layered.** A small core pack covers broad agent behaviors first. Domain packs for coding agents and ops/incident agents follow.

### Safety Regressions Must Be Obvious

When EvalForge flags a safety boundary violation, the reason should be immediately clear. Safety failures should never require investigation to understand what went wrong.

### v0.1 Posture

Credible for the launch pack, not feature-complete across all CUJs. The product earns trust through a small number of proven scenarios with strong default rubrics.

### What It Is Not

- Not a generic LLM eval framework
- Not a hosted observability platform
- Not an auto-prompt optimizer
- Not a benchmark leaderboard or vanity product

## Product Positioning

- **Framework-agnostic:** EvalForge is not tied to one runtime or orchestration system.
- **Python-friendly:** v0.1 should feel native for Python repos, local development, CI, and pytest-style workflows.
- **OSS-harness proven:** v0.1 must demonstrate working integrations with **two popular OSS agent frameworks**.
- **No unverified commercial claims:** do not claim support for commercial control planes or proprietary harnesses unless directly tested.

## Target Users

### Phase 1 - OSS Builder / Agent Engineer

- Maintains one or more tool-using agents in Python
- Ships changes frequently across prompts, tools, and models
- Needs release confidence beyond spot checks
- Wants local runs and CI-friendly evaluation

### Phase 2 - Agent Platform Team

- Supports multiple agent repos or multiple teams
- Needs shared scenario packs and common scoring rules
- Wants regression tracking across versions and frameworks
- Needs evidence for model swaps, prompt changes, and tool policy changes

## Success Metrics

- A team can run a repeatable evaluation suite for an agent change in one command.
- A new agent version can be compared to a baseline on correctness, trajectory quality, cost, latency, and policy behavior.
- EvalForge ships with **15-20 credible CUJs** that feel production-relevant rather than toy benchmarks.
- EvalForge demonstrates adapters or examples for **two OSS frameworks** in v0.1.
- CI can fail a release on regression thresholds rather than only on unit-test failures.

## Core Product Thesis

EvalForge should be opinionated about the evaluation shape, not about the runtime.

That means:

- common scenario format
- common run artifact format
- common scoring interfaces
- common regression comparison model
- pluggable adapters for different agent frameworks

The harness should not require a team to rewrite their agent. It should require them to expose enough structure to run and score it.

## Scope

### v0.1 - Evaluation Harness

| Capability | What it does |
|---|---|
| **Scenario pack format** | Defines tasks, inputs, context, allowed tools, expected outcomes, failure rules, and evaluation metadata |
| **Python CLI runner** | Runs an agent version against a scenario pack locally or in CI |
| **Adapter contract** | Lets different frameworks expose a normalized run artifact without EvalForge owning the runtime |
| **Trajectory capture model** | Stores steps, tool calls, arguments, outputs, timing, token usage, and judgeable events |
| **Scoring layer** | Scores correctness, task completion, tool use, argument quality, step efficiency, policy adherence, latency, and cost |
| **Regression comparison** | Compares candidate vs baseline by scenario family, metric, and failure cluster |
| **Evaluation reports** | Produces machine-readable JSON and human-readable markdown summaries |
| **Scenario tagging** | Groups scenarios by domain like tool-use, retrieval, coding, safety, budget, recovery, and multi-turn state |
| **Two OSS framework demos** | Ships tested examples for two popular OSS frameworks |

### Recommended OSS Framework Targets For v0.1

1. **LangGraph**
   - Strong evidence of market relevance as a low-level orchestration framework for long-running stateful agents.
   - Existing ecosystem interest in agent trajectory evaluation through `langchain-ai/agentevals` and LangSmith.

2. **PydanticAI**
   - Strong Python ergonomics and explicit investment in evals via `pydantic_evals`.
   - Clean fit for a Python-first eval harness with strong typed outputs and tool schemas.

### v0.2+ Expansion

- richer dataset authoring tools
- synthetic adversarial-case generation
- UI/dashboard for comparison browsing
- multi-agent and orchestrated topology packs
- hosted artifact storage or report viewer
- deeper integrations for CrewAI and other OSS frameworks

## Non-Goals

What EvalForge does **not** do in early versions:

| Non-Goal | Why |
|---|---|
| Replace runtime observability | EvalForge is for evaluation and regression discipline, not production tracing ownership |
| Become a generic benchmark zoo | The focus is practical agent evaluation, not infinite leaderboard collection |
| Auto-optimize prompts/models | EvalForge should diagnose and measure, not mutate systems automatically in v0.1 |
| Claim broad commercial harness support | Support claims must be proven with working adapters |
| Own every execution runtime | EvalForge should normalize artifacts from frameworks, not become another agent framework |

## Competitive / Adjacent Landscape

Research and repo review suggest a useful gap between existing categories:

| Tool / Repo | Strength | Gap EvalForge should address |
|---|---|---|
| **LangChain AgentEvals** (`langchain-ai/agentevals`) | Strong trajectory evaluators and graph-trajectory support | More evaluator library than end-to-end scenario/regression harness |
| **AWS Agent Evaluation** (`awslabs/agent-evaluation`) | Multi-turn evaluator/target orchestration, CI orientation | More AWS-shaped and evaluator-driven than framework-neutral local OSS harness |
| **Bananalyzer** (`reworkd/bananalyzer`) | High-quality web-task eval framing and dataset discipline | Narrow to browser/web tasks; EvalForge should generalize beyond web navigation |
| **DeepEval** (`confident-ai/deepeval`) | Broad metric catalog, framework integrations, pytest-style evals | General LLM eval framework; EvalForge should go deeper on scenario packs + trajectory/regression for agents |
| **PydanticAI evals** (`pydantic/pydantic-ai`) | Strong Python ergonomics and integrated eval thinking | Framework-specific; EvalForge should sit above individual runtimes |
| **Braintrust** | Strong eval/product category awareness | More platform-centric; EvalForge should be OSS-first, local-first, and agent-trajectory opinionated |

## Design Principles

1. **Trajectory over answer-only scoring**
   Final output matters, but path quality matters too.

2. **Scenario packs over ad hoc examples**
   Teams need reusable, tagged, versioned evaluation assets.

3. **Framework-neutral artifacts**
   A LangGraph run and a PydanticAI run should be comparable once normalized.

4. **Local-first workflow**
   The first happy path should work on a laptop and inside CI.

5. **Evidence over vibes**
   Release decisions need thresholds, diffs, and failure clusters.

## Core Workflows

### Workflow 1 - Compare Candidate vs Baseline

1. Developer registers a baseline and candidate agent version.
2. EvalForge runs the same scenario pack against both.
3. It computes per-scenario and aggregate metrics.
4. It reports where the candidate improved, regressed, or changed behavior.

### Workflow 2 - Gate a Release in CI

1. CI runs a tagged pack or a smoke subset.
2. EvalForge compares results against the accepted baseline.
3. Build fails if regression thresholds are exceeded.

### Workflow 3 - Diagnose a Regression Family

1. A new version fails a subset of scenarios.
2. EvalForge groups failures by tags like tool misuse, retrieval confusion, budget overrun, or policy break.
3. Developer inspects trajectory deltas and failing metrics.

### Workflow 4 - Add a New Scenario Pack

1. Team creates a scenario family for a production workload.
2. They define expected outputs, tool constraints, policy rules, and scoring strategy.
3. Pack becomes reusable across versions and possibly across frameworks.

## Metrics That Matter

EvalForge should not try to invent every metric. It should emphasize a compact, credible set for agents:

- **Task completion**
- **Output correctness**
- **Trajectory quality**
- **Tool selection quality**
- **Tool argument correctness**
- **Step efficiency**
- **Policy / safety adherence**
- **Latency budget adherence**
- **Cost budget adherence**
- **Recovery quality after failure or ambiguity**

Implementation details for data models, scoring behavior, launch-pack shape, and adapter targets live in `docs/spec.md`.

## Canonical User Journeys (CUJs)

These CUJs intentionally target a broader product surface than v0.1 will fully implement. They define the scenario ambition and evaluation surface.

### 1. Single-Tool Factual Retrieval

- **Goal:** Verify that the agent can solve a bounded lookup task with the right tool and minimal ceremony.
- **Customer journey:** Developer selects a retrieval pack, points EvalForge at an agent version, and sees whether the agent chose the right tool, passed the right query, and answered correctly.
- **Example user story:** "As an agent engineer, I want to know whether my support agent can answer a straightforward account-policy question with one correct retrieval call."
- **Failure modes:** wrong tool, duplicate calls, over-querying, incorrect answer despite correct retrieval, fabricated answer with no retrieval.
- **Primary success metrics:** task completion, output correctness, tool correctness, step efficiency, latency.

### 2. Multi-Tool Retrieval Synthesis

- **Goal:** Verify that the agent can combine evidence from multiple sources without dropping or distorting key facts.
- **Customer journey:** Team runs a scenario where the answer requires two or more retrieval operations, then inspects whether the synthesis was grounded and complete.
- **Example user story:** "As a platform team, I want to compare two versions of a research agent on source fusion tasks, not just single-lookups."
- **Failure modes:** only one source consulted, contradictory facts merged incorrectly, unsupported synthesis, answer omits critical retrieved evidence.
- **Primary success metrics:** task completion, answer faithfulness, completeness, tool sequence quality, cost.

### 3. Structured JSON Extraction

- **Goal:** Verify that the agent can transform messy input into reliable machine-readable output.
- **Customer journey:** Builder defines expected schema and validates whether the agent returned structurally valid and semantically correct JSON.
- **Example user story:** "As a builder, I want to know if my extraction agent still emits a schema-valid object after a prompt change."
- **Failure modes:** schema invalid output, partial extraction, wrong field mapping, hallucinated fields, correct schema but semantically wrong values.
- **Primary success metrics:** schema validity, field-level correctness, hallucination rate, retry count, latency.

### 4. Tool Argument Precision

- **Goal:** Separate tool selection quality from tool argument quality.
- **Customer journey:** Team runs a task where the tool is obvious but argument construction is error-prone, then reviews argument-level diffs.
- **Example user story:** "As an engineer, I want to catch cases where the agent picked the right API but passed the wrong repo, branch, or date range."
- **Failure modes:** malformed arguments, over-broad arguments, unsafe defaults, missing required params, semantically wrong but syntactically valid args.
- **Primary success metrics:** argument correctness, tool correctness, policy adherence, task completion.

### 5. Tool Avoidance When No Tool Is Needed

- **Goal:** Verify that the agent does not turn easy tasks into expensive workflows.
- **Customer journey:** Team runs a lightweight question pack and checks whether the agent uses tools only when needed.
- **Example user story:** "As an operator, I want my agent to answer simple policy questions without paying for unnecessary retrieval calls."
- **Failure modes:** needless tool invocation, repeated tool use, inflated latency, increased cost with no quality gain.
- **Primary success metrics:** step efficiency, cost, latency, output correctness.

### 6. Disallowed Tool Refusal

- **Goal:** Verify that the agent respects tool policy boundaries under pressure.
- **Customer journey:** Security-sensitive scenario prompts the agent toward a prohibited action; EvalForge scores whether the agent refuses correctly.
- **Example user story:** "As a security-minded team, I want evidence that my agent refuses production-write tools in unapproved contexts."
- **Failure modes:** prohibited tool call, partial execution before refusal, weak explanation, unsafe alternative suggestion.
- **Primary success metrics:** policy adherence, refusal quality, zero disallowed actions, task safety classification.

### 7. Ambiguous User Request Clarification

- **Goal:** Verify that the agent asks before it acts when ambiguity changes outcome or risk.
- **Customer journey:** Team runs ambiguous prompts and inspects whether the agent clarifies instead of guessing.
- **Example user story:** "As a product engineer, I want my agent to ask whether the user means staging or production before it proposes any action."
- **Failure modes:** premature action, guessed assumptions, unsafe tool execution, clarifying question asked too late.
- **Primary success metrics:** clarification quality, unsafe action avoidance, trajectory quality, task completion after clarification.

### 8. Hallucination Resistance Under Missing Data

- **Goal:** Verify that the agent degrades honestly when evidence is absent.
- **Customer journey:** Team evaluates scenarios with intentionally missing evidence and checks whether the agent states uncertainty correctly.
- **Example user story:** "As a team lead, I want to know if my agent admits it doesn't know rather than fabricating status or metrics."
- **Failure modes:** fabricated facts, false certainty, fake tool result interpretation, unsupported recommendation.
- **Primary success metrics:** hallucination rate, uncertainty handling quality, policy adherence, answer trustworthiness.

### 9. Retrieval Conflict Resolution

- **Goal:** Verify that the agent can detect and communicate evidence conflicts.
- **Customer journey:** Team runs a scenario with conflicting retrieval results and reviews whether the agent surfaced the disagreement.
- **Example user story:** "As an operations engineer, I want my agent to flag when two systems disagree on incident status instead of presenting one as fact."
- **Failure modes:** conflict ignored, wrong source over-trusted, overconfident answer, unsupported tie-breaker logic.
- **Primary success metrics:** conflict detection, reasoning quality, answer calibration, retrieval faithfulness.

### 10. Long-Context State Recall

- **Goal:** Verify that the agent preserves important state through extended interactions.
- **Customer journey:** Team evaluates multi-turn tasks where details introduced earlier matter later.
- **Example user story:** "As a builder, I want to know if my agent remembers the user's chosen environment and constraints ten steps later."
- **Failure modes:** dropped facts, state drift, mixed identities, repeated questions for known context.
- **Primary success metrics:** memory retention, turn relevance, task completion, trajectory consistency.

### 11. Memory Contamination Resistance

- **Goal:** Verify that memory helps rather than harms later decisions.
- **Customer journey:** Team runs scenarios with stale or misleading prior context and checks whether the agent correctly ignores it.
- **Example user story:** "As an engineer, I want my agent to stop carrying over an earlier branch name or customer account into a later unrelated task."
- **Failure modes:** stale-memory reuse, wrong entity carryover, over-personalization, leakage across tasks.
- **Primary success metrics:** context isolation, entity correctness, task completion, contamination rate.

### 12. Budget-Constrained Completion

- **Goal:** Verify that the agent can trade off completeness and efficiency within explicit limits.
- **Customer journey:** Team sets budget thresholds and evaluates whether the candidate version stays inside them without collapsing quality.
- **Example user story:** "As an owner, I want to know whether a new prompt improves quality without doubling token spend."
- **Failure modes:** runaway loops, too many tools, hidden retries, perfect answers at unacceptable cost, early abort with no fallback.
- **Primary success metrics:** cost budget adherence, token usage, step efficiency, task completion, cost-quality ratio.

### 13. Graceful Timeout / Partial-Failure Recovery

- **Goal:** Verify that the agent recovers cleanly from one failing dependency instead of collapsing or looping.
- **Customer journey:** Team injects tool timeout or partial outage into a run and reviews retry and fallback behavior.
- **Example user story:** "As an SRE, I want my agent to explain the degraded answer when one backend times out rather than looping forever."
- **Failure modes:** infinite retries, silent drop of failed tool, fabricated success, no fallback path, user receives no explanation.
- **Primary success metrics:** recovery quality, retry discipline, timeout handling, user-visible explanation quality, task completion under degradation.

### 14. Safe External Action Approval Boundary

- **Goal:** Verify that the agent stops at approval boundaries for sensitive actions.
- **Customer journey:** Team runs execution scenarios involving side effects and checks whether the agent pauses for approval.
- **Example user story:** "As a platform owner, I need evidence that the agent will not merge, deploy, or page without an approval checkpoint."
- **Failure modes:** action executed without approval, approval requested after side effects, weak justification, confusing pause state.
- **Primary success metrics:** approval-boundary adherence, zero unauthorized actions, pause fidelity, explanation quality.

### 15. Code Change Impact Analysis

- **Goal:** Verify that a coding agent can reason about downstream impact, not just summarize a diff.
- **Customer journey:** Team provides a code change and checks whether the agent identifies affected modules, tests, and risks.
- **Example user story:** "As a reviewer, I want the agent to tell me what this change could break and what should be verified next."
- **Failure modes:** shallow summary only, missed dependencies, irrelevant risks, no verification plan.
- **Primary success metrics:** blast-radius accuracy, verification recommendation quality, relevance, completeness.

### 16. Test Failure Diagnosis

- **Goal:** Verify that the agent can perform disciplined debugging rather than surface-level pattern matching.
- **Customer journey:** Team supplies failing logs and repository context, then compares root-cause hypotheses across versions.
- **Example user story:** "As an infra engineer, I want the agent to read the right logs, inspect the right code, and give me a plausible cause with evidence."
- **Failure modes:** generic diagnosis, wrong evidence source, hallucinated root cause, no confidence calibration, no next checks.
- **Primary success metrics:** hypothesis quality, evidence grounding, investigative path quality, next-step usefulness.

### 17. Multi-Step Repo Task Completion

- **Goal:** Verify that a repo agent can stay scoped on an engineering task across multiple decisions.
- **Customer journey:** Team gives a realistic engineering task and scores whether the agent inspected the right files and stayed on-target.
- **Example user story:** "As a staff engineer, I want the agent to stay within the requested change boundary and not refactor half the repo."
- **Failure modes:** scope drift, missed file dependencies, incomplete plan, irrelevant edits, missing verification.
- **Primary success metrics:** scope adherence, task completion quality, plan quality, verification completeness.

### 18. Runbook / Incident Retrieval

- **Goal:** Verify that the agent can retrieve and apply the right operational guidance under pressure.
- **Customer journey:** Team runs incident scenarios and checks whether the agent finds the right runbook and follows supported actions.
- **Example user story:** "As an on-call engineer, I want the agent to point me to the right recovery steps without inventing commands."
- **Failure modes:** wrong runbook, unsupported fix, dangerous remediation, no escalation guidance, stale playbook use.
- **Primary success metrics:** runbook match accuracy, safety adherence, remediation relevance, escalation quality.

### 19. Web Task Information Retrieval

- **Goal:** Verify browser-task competence in dynamic or multi-page environments.
- **Customer journey:** Team runs web retrieval tasks against stable snapshots or controlled environments and compares navigation paths.
- **Example user story:** "As a team building browser agents, I want to know whether the agent can actually find pricing, docs, or listing details reliably."
- **Failure modes:** navigation loops, wrong page interpretation, missed pagination, brittle selector behavior, overlong paths.
- **Primary success metrics:** task completion, navigation efficiency, extraction correctness, robustness across page variants.

### 20. Orchestrated Subtask Evaluation

- **Goal:** Verify that an orchestrated workflow completes correctly and that delegated subtasks stay within contract.
- **Customer journey:** Team evaluates a parent flow plus child steps and inspects whether failures came from planning, delegation, or execution.
- **Example user story:** "As a multi-agent builder, I want to know whether the coordinator decomposed the problem well and whether each substep stayed within its role."
- **Failure modes:** bad decomposition, wrong subtask order, duplicated work, context leakage between subtasks, local success but global failure.
- **Primary success metrics:** end-to-end task completion, decomposition quality, subtask boundary adherence, aggregate cost and latency, failure attribution quality.

## Why These CUJs Matter

The CUJs above cover the real behaviors that make agent evaluation difficult:

- answer quality
- trajectory quality
- tool discipline
- budget discipline
- safety boundaries
- recovery behavior
- code-agent behavior
- browser or environment interaction
- state across turns

Even if v0.1 ships only a subset, the PRD should anchor on this broader surface so the project does not collapse into a toy metric runner.

## Initial Scenario Families To Ship First

For the first practical pack set, prioritize these families:

1. retrieval and synthesis
2. tool choice and tool arguments
3. budget / step efficiency
4. ambiguity and refusal behavior
5. coding-agent regression scenarios
6. recovery from tool failure


## Open Questions

- What is the minimum normalized run artifact required across frameworks?
- Which metrics should be deterministic vs LLM-as-judge in v0.1?
- Should scenario packs support both exact-reference scoring and rubric-based scoring from day one?
- What is the right storage format for results: local JSON only, SQLite, or optional Postgres?
- Should baseline comparisons be stored by git SHA, semantic version, or arbitrary named run?
- What subset of CUJs becomes the official launch pack?

## References

- `langchain-ai/agentevals` - strong trajectory evaluator patterns and graph trajectory support
- `awslabs/agent-evaluation` - evaluator/target model with multi-turn testing and CI posture
- `reworkd/bananalyzer` - credible web-task eval framing, static snapshots, and scenario discipline
- `confident-ai/deepeval` - broad metric surface and framework integrations for agents
- `pydantic/pydantic-ai` - Python-native agent framework with explicit eval investment
- `langchain-ai/langgraph` - important OSS target framework for stateful agent workflows
- `crewAIInc/crewAI` - important OSS framework to study, but not required as a proven v0.1 target
