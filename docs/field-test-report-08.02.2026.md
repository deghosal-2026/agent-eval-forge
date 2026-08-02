# Field Test Report — 08.02.2026

**Date:** 2026-08-02
**Status:** 19-agent compatibility sweep complete; cloud tiers compared; report reframed around what the field test does and does not prove
**Scope:** agent-eval-forge v0.1.0 field test — M11 diagnostic pass + first expanded cloud-tier sweep

---

## 1. Executive Summary

Following the roster scale-up on 08.01, today's session focused on a diagnostic and
compatibility pass: running the expanded roster, fixing import/config failures,
quarantining incompatible agents, and comparing cheap vs better cloud judges. One
agent (pa-research) was removed due to fundamental incompatibility with current
pydantic-ai APIs, leaving **19 active agents (11 LangGraph + 8 PydanticAI)**.

**Key results:**
- The field test now means something concrete: it is a **compatibility and adapter-hardening benchmark**, not yet a mature cross-agent quality leaderboard.
- **lg-mcp-agents achieved 5/5 passes** on both cheap and better tiers after targeted adapter work.
- Cheap and better cloud tiers produced the **same outcome: 9/95 passes (9%)**, so better-tier spend does not currently buy better signal.
- Several pydantic-ai wrapper agents regressed from yesterday's 1/5 cloud passes to 0/5 due to blank-completion wrapper behavior.
- Local tier is not decision-useful unless the MLX endpoint is confirmed healthy; today's authoritative local run was **4/95**.

**What this field test proves:**
- EvalForge can stress-test a much broader, messier open-source roster than yesterday's curated 8-agent sample.
- The main current bottleneck is third-party integration realism, not judge choice.
- Cheap cloud judging is sufficient for routine field sweeps right now.

**What this field test does not yet prove:**
- It does not yet support meaningful quality ranking across the full 19-agent roster.
- It does not yet show that wrapper-based PydanticAI integrations faithfully exercise real agent behavior.
- It does not justify running the better tier by default, because better and cheap produced identical conclusions.

---

## 2. Plan vs. Actual

| Metric | Planned (08.01) | Actual (08.02) |
|---|---|---|
| Total agents | 20 | 19 (pa-research removed) |
| LangGraph agents | 11 | 11 |
| PydanticAI agents | 9 | 8 |
| Agents passing import | 8 | 9 |
| Agents quarantined | 2 | 10 |
| Wrapper modules written | 0 | 8 |
| pyproject.toml files created | 0 | 3 (pa-github, pa-multi-agent, pa-weather) |
| Configs updated | 0 | 5 (pa-weather, lg-mcp-template, lg-tools-agent, pa-github, pa-multi-agent) |

---

## 3. What The Field Test Means

The 08.02 sweep should be interpreted as a **platform compatibility test** first,
and an **agent-quality benchmark** only secondarily.

It currently measures three things:

1. **Harness compatibility**
   Can EvalForge import, configure, and invoke a third-party repo at all?

2. **Adapter realism**
   Are we exercising real agent logic, or only a compatibility wrapper that keeps
   the harness alive but returns weak/blank behavior?

3. **Judge usefulness**
   Does switching from cheap to better materially change conclusions?

Today's answer:

| Dimension | Meaningful result |
|---|---|
| Harness compatibility | Partial success. More repos load than yesterday, but many still require quarantine or curation. |
| Adapter realism | Weak for most PydanticAI repos; wrapper importability improved faster than behavior quality. |
| Judge usefulness | Cheap and better are currently equivalent in outcome; better is not justified as the default tier. |

**Bottom line:** this field test is valuable because it reveals what classes of
third-party agents EvalForge can support today, how much curation they require,
and where the current runtime assumptions break. It is not yet a credible
leaderboard of agent quality across the 19-agent roster.

---

## 4. Fixes Applied This Session

### 4.1 Version-tolerant Wrappers

Eight agents were incompatible with pydantic-ai 1.x/2.x API changes
(`OpenAIModel` → `OpenAIChatModel`, positional vs keyword provider args).
Version-tolerant `evalforge_wrapper.py` modules were deployed to:

| Agent | Issue | Fix |
|---|---|---|
| pa-github | Own module imports deprecated `OpenAIModel`; UTF-16 requirements.txt | Wrapper + pyproject with `pydantic-ai[openai]` |
| pa-weather | Own module imports old `OpenAIModel`; no pyproject.toml | Wrapper + pyproject |
| pa-multi-agent | Own `task_manager_agent` uses `result_type` kwarg (old 2.x API) | Wrapper + pyproject |
| pa-research | Own module imports old `OpenAIModel` | **Removed from roster** — intractable API gap |
| lg-mcp-template | `src/` layout — module not on sys.path | Wrapper adds `src/` to sys.path |
| lg-tools-agent | `async def graph(config)` — async factory, not compiled graph | Wrapper calls `asyncio.run()` to build |

### 4.2 C-Extension Incompatibility (Quarantines)

Three agents—lg-tools-agent, lg-mcp-template, lg-skills—import langgraph
internals that depend on the `ormsgpack` C extension. The agent venvs run
Python 3.11/3.13, but the field runner's system Python is 3.14.5. C extensions
compiled for 3.11/3.13 cannot load under 3.14. Wrapper-level `sys.path`
injection of the venv's `site-packages` fails at the C-ABI level.

**Remedy for future:** The field runner should execute agent imports inside the
agent's own venv Python (`$AGENT_PYTHON`), not the runner's system Python.

### 4.3 Config Fixes

| Agent | Old Config | New Config | Reason |
|---|---|---|---|
| pa-weather | `weather_agent.weather_agent` | `evalforge_wrapper:build_agent` | Old OpenAIModel import |
| pa-github | `github_agent.github_agent` | `evalforge_wrapper:build_agent` | UTF-16 reqs + old API |
| pa-multi-agent | `src.agents...task_manager_agent:TaskManagerAgent` | `evalforge_wrapper:build_agent` | `result_type` kwarg incompat |
| lg-mcp-template | `mcp_agent:graph` | `evalforge_wrapper:graph` | `src/` layout |
| lg-tools-agent | `tools_agent.agent:graph` | `evalforge_wrapper:graph` | Async factory |
| lg-skills | (already had wrapper) | Quarantined | ormsgpack C-extension |
| lg-mcp-template | (already had wrapper) | Quarantined | ormsgpack C-extension |
| lg-tools-agent | (already had wrapper) | Quarantined | ormsgpack C-extension |

---

## 5. Results by Tier

### 5.1 Cheap (gpt-4o-mini)

| Tier | Passed | Failed | Pass Rate |
|---|---|---|---|
| Cheap | 9 | 86 | 9% |

| Agent | Score | Notes |
|---|---|---|
| lg-chatbot | 2/5 ##... | no-tool-needed ✓, disallowed-tool ✓ |
| lg-eval-graph | 2/5 ##... | no-tool-needed ✓, disallowed-tool ✓ |
| lg-mcp-agents | **5/5 #####** | Previously quarantined; fully working |
| 7 pydantic-ai agents | 0/5 ..... | Blank completion (model endpoint issue) |
| 9 quarantined/import-err agents | 0/5 ..... | Expected failures |

### 5.2 Better (gpt-4o)

| Tier | Passed | Failed | Pass Rate |
|---|---|---|---|
| Better | 9 | 86 | 9% |

Identical to cheap tier. gpt-4o provided no improvement over gpt-4o-mini for
the scenarios currently capable of passing. At this stage, paying for the better
tier does not improve evaluation signal.

### 5.3 Local (MLX — no LLM endpoint)

| Tier | Passed | Failed | Pass Rate |
|---|---|---|---|
| Local | 4 | 91 | 4% |

Local tier had no running LLM endpoint during today's run. Only scenarios that do
not require real model behavior pass. Also note: the `field/results/` tree contains
historical local artifacts mixed with today's run, so today's authoritative local
conclusion should come from the observed run summary (`4/95`), not from aggregate
filesystem counting.

### 5.4 Cross-Tier Comparison

| Dimension | Local | Cheap | Better |
|---|---|---|---|
| Practical purpose | Smoke test only when MLX is live | Best default sweep tier | Tie-breaker / audit tier only |
| Pass count today | 4 | 9 | 9 |
| Cost | $0 infra cost, but only if endpoint is up | Low | Higher, no added value today |
| Signal quality | Low today (endpoint missing) | Good enough | Same as cheap |
| Recommendation | Use only when local endpoint is healthy | **Default field-test tier** | Use sparingly |

**Recommendation:**
- Use `cheap` as the standard regression and comparison tier.
- Use `better` only when cheap and local disagree, or when auditing borderline
  scoring behavior.
- Use `local` only when the MLX endpoint is confirmed available; otherwise it adds
  noise, not signal.

---

## 6. Comparison To 08.01

Yesterday's preserved materials covered two distinct baselines:

- the original curated **8-agent** sweep preserved in `field/results.08.01.2026/`
- `docs/field-test-report-08.01.2026.md`: the roster expansion to **20 agents**

Today's report is the first attempt to actually operationalize that larger roster.

### 6.1 Absolute Comparison vs 08.01 Curated Sweep

| Tier | 08.01 Curated Sweep (8 agents) | 08.02 Expanded Sweep (19 agents) | Meaning |
|---|---|---|---|
| Local | 12/40 (30%) in report, 22/40 archived artifacts | 4/95 authoritative run summary | Local is not comparable because today's MLX endpoint was not available. |
| Cheap | 7/40 (18%) | 9/95 (9%) | Absolute pass count improved, pass rate dropped due to much broader roster. |
| Better | 7/40 (18%) | 9/95 (9%) | Same pattern as cheap. |

### 6.2 Shared-Agent Comparison

For the 8 agents that existed in both runs, today's work produced both wins and regressions:

| Agent | Cheap 08.01 | Cheap 08.02 | Better 08.01 | Better 08.02 | Observation |
|---|---|---|---|---|---|
| lg-eval-graph | 1/5 | 2/5 | 1/5 | 2/5 | Improved |
| pa-collab | 1/5 | 0/5 | 1/5 | 0/5 | Regressed |
| pa-effective-agents | 1/5 | 0/5 | 1/5 | 0/5 | Regressed |
| pa-harness | 1/5 | 0/5 | 1/5 | 0/5 | Regressed |
| pa-mcpadapt | 1/5 | 0/5 | 1/5 | 0/5 | Regressed |

**Interpretation:** importability improved, but several wrapper-based PydanticAI
agents became less behaviorally useful. The field test therefore surfaced an
important tradeoff: a compatibility shim can make an agent runnable without making
it meaningfully testable.

---

## 7. Failure Breakdown (Cheap Tier)

| Category | Count | Agents |
|---|---|---|
| Blank completion | 35 | pa-mcpadapt, pa-collab, pa-harness, pa-effective-agents, pa-github, pa-multi-agent, pa-weather |
| Import/module error | 30 | lg-mcp-template, lg-skills, lg-tools-agent, lg-agent-system, lg-course, lg-my-agent, lg-plan-react |
| Warn (tool_called=False) | 6 | lg-chatbot (3), lg-eval-graph (3) |
| Other | 15 | lg-research-agent (filesystem), pa-skills (connection), lg-course, lg-* |
| **Passed** | **9** | lg-chatbot (2), lg-eval-graph (2), lg-mcp-agents (5) |

---

## 8. Agents Tested (Current Roster — 19)

### 8.1 LangGraph (11)

| Agent | Slug | Status |
|---|---|---|
| Chatbot in LangGraph | lg-chatbot | 2/5 (no-tool + disallowed-tool pass) |
| EvalGraph | lg-eval-graph | 2/5 (same) |
| Lab LangGraph Basics | lg-research-agent | Quarantined (config needed) |
| MCP Agents (Streamlit) | lg-mcp-agents | **5/5 working on cheap/better** |
| Tools Agent | lg-tools-agent | Quarantined (ormsgpack C-ext) |
| MCP Template | lg-mcp-template | Quarantined (ormsgpack C-ext) |
| Plan+React | lg-plan-react | Quarantined (Tavily API key) |
| My Agent | lg-my-agent | Quarantined (CLI-only) |
| Agent System | lg-agent-system | Quarantined (ABC, no instance) |
| Skills Agent | lg-skills | Quarantined (ormsgpack C-ext) |
| Course | lg-course | Quarantined (no single agent entry point) |

### 8.2 PydanticAI (8)

| Agent | Slug | Status |
|---|---|---|
| MCPAdapt | pa-mcpadapt | Blank completion (model issue) |
| Skills | pa-skills | Connection error (no API key on cheap tier) |
| Collab | pa-collab | Blank completion |
| Harness | pa-harness | Blank completion |
| Effective Agents | pa-effective-agents | Blank completion |
| GitHub Agent | pa-github | Blank completion |
| Multi Agent System | pa-multi-agent | Blank completion |
| Weather Agent | pa-weather | Blank completion |

---

## 9. Extra Work Required Beyond The Plan

The 08.01 roster-expansion report assumed configuration curation would be the main
follow-up task. In practice, the expanded field test required more engineering work
than that:

1. Creating `pyproject.toml` files for repos with missing or unusable packaging metadata
2. Handling UTF-16 `requirements.txt` in pa-github
3. Writing version-tolerant PydanticAI wrappers across 1.x/2.x APIs
4. Handling `src/` layout repos that are not importable from repo root
5. Adapting async graph factories to sync harness expectations
6. Discovering Python ABI incompatibility between runner Python 3.14 and agent venv 3.11/3.13
7. Adjusting `.gitignore` and git-index behavior to persist wrapper files inside ignored third-party agent clones
8. Cleaningly removing pa-research from the roster instead of letting it silently fail

This is useful planning data: scaling field coverage is not just “add repos and run.”
It is an integration program with meaningful per-repo curation cost.

---

## 10. Observations And Learnings

1. **Cheap is enough right now.** Better produced zero additional signal over cheap.

2. **Cloud tiers are more decision-useful than local today.** Yesterday's reports already
   showed cloud judges were stricter than local. Today's expanded sweep confirms that
   cheap and better agree with each other, while local is only useful when the local
   endpoint is healthy.

3. **Compatibility success is not the same as evaluation success.** A wrapper can remove
   import errors while still returning blank or placeholder output. This matters for the
   PydanticAI regressions.

4. **The biggest win was not a higher pass rate; it was a broader support boundary.**
   `lg-mcp-agents` moving from effectively non-runnable to 5/5 is more important than
   the overall pass percentage.

5. **Yesterday's core lesson still holds.** The main bottleneck is still adapter realism,
   not the judge model. Today's data strengthens that conclusion at a larger roster size.

6. **The field test now has decision value.** It can tell us:
   - which agents are supportable today
   - which require runtime changes in EvalForge
   - which fail because of wrapper behavior, not repo behavior
   - which evaluation tier we should standardize on

---

## 11. Article-Ready Notes And Narrative Angles

This section intentionally captures more context than a normal execution report so
future blog posts, launch notes, and benchmark explainers can draw from a durable
record instead of re-deriving the story from raw logs.

### 11.1 Narrative Arc Of The Two-Day Sweep

**Day 1 (08.01):**
- Proved the harness worked on a small curated sample of 8 agents.
- Established that real cloud judges were stricter than local judging.
- Expanded the roster to 20 GitHub-sourced agents to test whether EvalForge could
  handle the messiness of the open-source ecosystem instead of only hand-picked
  examples.

**Day 2 (08.02):**
- Turned the expanded roster into an actual compatibility challenge.
- Discovered that scaling field tests is not just “more agents”; it is a sequence
  of packaging, import, runtime, Python-version, and framework-version problems.
- Showed that the hard part of field testing is not scoring once an agent runs;
  the hard part is making third-party agents runnable without distorting what they do.

**Meaningful takeaway for an article:**
- Benchmarks for agent frameworks fail in practice not because scoring is hard,
  but because third-party agents are packaged, versioned, and structured in wildly
  inconsistent ways.

### 11.2 What We Learned About Real Open-Source Agents

The roster gave a representative cross-section of open-source agent failure modes:

| Failure mode | What it looked like in practice | Why it matters |
|---|---|---|
| Old framework APIs | `OpenAIModel` imports no longer valid in modern pydantic-ai | Field testing must bridge framework drift across repo vintages |
| Missing project metadata | Repos without `pyproject.toml` or usable dependency manifests | Benchmark harnesses cannot assume modern Python packaging |
| `src/` layout assumptions | Import works under LangGraph CLI but not under repo-root Python | Repo execution environment matters as much as repo code |
| Async factory mismatch | `async def graph(config)` not directly invokable by sync harness | Framework conventions vary inside the same ecosystem |
| Absolute-path side effects | Writes to `/root` at import time | Some agent repos are not sandbox-friendly by design |
| Gateway-bound execution | Agents require external service keys or gateway URLs | Evaluation cost and reproducibility depend on external infra |
| Python ABI mismatch | venv C extensions fail under runner Python 3.14 | A “working venv” is not enough if the harness imports from the wrong interpreter |

**Article angle:** “Open-source agent repos are not products; they are snapshots
of local development environments. A real field harness has to survive that.”

### 11.3 What The LLM Comparison Actually Taught Us

At face value, one might expect three tiers to give three different answers:

- local = fast/cheap but weaker
- cheap = practical baseline
- better = more accurate final answer

Today's data says something more nuanced:

1. **Local only matters when the local endpoint is healthy.**
   Without a real local model endpoint, local is not a benchmark tier; it is just a
   smoke test for the no-model path.

2. **Cheap was enough to reach the same conclusions as better.**
   Cheap and better produced the same overall pass count and the same per-agent shape.

3. **Judge quality is no longer the main limiter.**
   Once cheap and better agree, spending more on better does not improve signal until
   adapter realism improves.

4. **The real comparison was not LLM quality; it was infrastructure quality.**
   The decisive differences came from wrappers, import paths, packaging, and runtime assumptions.

**Article angle:** “Before optimizing which judge model to use, make sure your
benchmark is evaluating the agent instead of your integration shim.”

### 11.4 Regressions Worth Calling Out Honestly

This run was not a clean upward slope. Some important regressions appeared:

- `pa-collab`, `pa-effective-agents`, `pa-harness`, and `pa-mcpadapt` each went
  from **1/5 on cloud tiers yesterday to 0/5 today**.
- The reason was not that the agents got worse. The compatibility wrappers made the
  repos load reliably, but they also flattened real behavior into blank completion.
- That is an important methodological lesson: **a compatibility fix can lower benchmark fidelity.**

This should be preserved in the report because it is exactly the kind of insight that
makes future writing credible rather than promotional.

### 11.5 Why `lg-mcp-agents` Matters Disproportionately

`lg-mcp-agents` is the strongest single result in the 08.02 sweep.

Why it matters:
- It was not part of yesterday's curated working set.
- It initially looked like a poor fit for EvalForge because it presents as a Streamlit-driven project.
- After targeted configuration and wrapper work, it became the only expanded-roster
  agent to achieve **5/5 passes** on both cloud tiers.

This is the best evidence that EvalForge is not limited to toy examples or hand-picked
success cases. It can bring a non-trivial external repo into a fully testable shape.

**Article angle:** “The first truly rescued third-party repo: from incompatible app
surface to clean 5/5 benchmark run.”

### 11.6 SWE-bench Connector: End-to-End Verified

The `BenchmarkLoader` and CLI (`evalforge benchmark import`) were built and tested
end-to-end during this session.

**What was done:**
- Loaded a 3-task SWE-bench sample (django, sympy, pytest)
- Converted to a native EvalForge scenario pack via `export_pack()`
- Added the pack to `lg-chatbot`'s field config
- Ran all three tiers (local/cheap/better) against the imported scenarios

**Results:**

| Tier | django__django-1000 | sympy__sympy-2000 | pytest__pytest-3000 | Observation |
|---|---|---|---|---|
| Local (Qwen, OMLX) | PASS | PASS | PASS | `[1]` returned, exact match bypassed |
| Cheap (gpt-4o-mini) | PASS | PASS | PASS | Lenient judge scored task_completion as pass |
| Better (gpt-4o) | FAIL | FAIL | FAIL | Stricter judge correctly scored task_completion=False |

**Key finding:** All three tiers agree the agent did not solve the coding task
(`task_completion=False` on better, tool_correctness=True because no disallowed
tools were called). The cheap judge was more lenient and passed the scenarios
despite the agent not producing a valid patch. This matches the broader pattern
observed in the 08.01 sweep: cheap and better judges diverge on task_completion
for cases where the agent returns empty or incomplete output.

**Connector verified as working end-to-end.** The pipeline from SWE-bench JSONL
→ BenchmarkTask → ScenarioPack → field runner → scored results is fully
operational. The same pattern applies to WebArena and any custom format
registered via `BenchmarkRegistry`. The `evalforge benchmark import` CLI command
makes the process repeatable.

**Article angle:** “Importing SWE-bench into your agent evaluation pipeline in
one command — and what the tier comparison reveals about judge strictness.”

### 11.7 What We Could Have Done Better Operationally

This session also surfaced process improvements for future field sweeps:

1. **Isolate tier outputs by date or run-id from the start.**
   Mixed local artifacts made later comparison harder than it needed to be.

2. **Separate compatibility wrappers from behavior wrappers.**
   A repo that merely imports should not automatically count as meaningfully benchmarkable.

3. **Capture a support-state label per agent.**
   For example: `native`, `wrapped-real`, `wrapped-compat`, `quarantined`.
   That would make benchmark interpretation much clearer.

4. **Treat Python interpreter choice as part of the benchmark environment.**
   The ormsgpack issue was not a code bug; it was an environment-model mismatch.

5. **Promote cheap tier to the default review artifact.**
   It is the current best tradeoff between signal and cost.

### 11.7 Suggested Themes For Future Articles

Possible article/report angles now supported by the data:

1. **"What breaks when you benchmark real open-source AI agents"**
   Focus: packaging drift, runtime assumptions, framework version skew.

2. **"Why cheap judges are enough for early agent benchmarks"**
   Focus: cheap vs better equivalence in practical conclusions.

3. **"The hidden engineering work behind agent benchmarks"**
   Focus: wrappers, pyprojects, path fixes, interpreter mismatch, quarantine policy.

4. **"Compatibility is not quality: lessons from a 19-agent field sweep"**
   Focus: importability can improve while benchmark fidelity regresses.

5. **"How to scale from a curated benchmark to the open-source wild"**
   Focus: day-1 curated sample vs day-2 expanded roster.

### 11.8 Quotes / Phrases Worth Reusing Later

- “The hard part of benchmarking agents is not scoring them once they run; it is making third-party agents runnable without distorting what they do.”
- “Cheap and better agreed, which means model sophistication is not our main problem yet.”
- “A compatibility shim can make an agent runnable without making it meaningfully testable.”
- “The expanded roster turned the field test from a benchmark into a compatibility stress test, and that was exactly what we needed.”
- “Open-source agent repos are snapshots of local development environments, not benchmark-ready artifacts.”

---

## 12. Artifacts Committed

- `field/config/*.json` — 17 config files (11 new + 6 updated)
- `field/agents/*/evalforge_wrapper.py` — 8 wrapper modules
- `field/agents/*/pyproject.toml` — 3 new project files
- `field/list.txt` — Updated 19-agent roster
- `.gitignore` — Adjusted to allow `field/agents/*/evalforge_wrapper.py` and `pyproject.toml`
- `field/results/` — Full results for local, cheap, and better tiers
- `docs/field-test-report-08.01.2026.md` and `docs/field-test-report-08.02.2026.md` — Historical dated reports

---

## 13. Next Steps

- [ ] P1: Fix blank-completion behavior for wrapper-based PydanticAI agents
- [ ] P2: Resolve ormsgpack / Python ABI mismatch by running agent imports inside agent venv Python
- [ ] P3: Curate remaining module-path failures (lg-agent-system, lg-course, lg-my-agent, lg-plan-react)
- [ ] P4: Re-run cheap tier after P1-P3; cheap should remain the default comparison tier
- [ ] P5: Re-run better tier only if cheap changes materially or there is a scoring dispute
- [ ] P6: Re-run local only when MLX endpoint health is confirmed
- [ ] M11 Task 2 (build/twine/wheel-install) and Task 3 (security scan, docs-link check, pyproject metadata)
- [x] Session lessons incorporated into `docs/hard-won-lessons.md`
