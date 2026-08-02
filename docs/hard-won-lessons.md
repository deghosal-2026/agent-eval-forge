# Hard-Won Lessons

Real-world lessons from building and field-testing EvalForge against 19+
open-source LangGraph and PydanticAI agents from GitHub. Organized by theme,
not chronology.

---

## 1. Third-Party Agent Integration

### 1.1 Bad patterns in third-party agents

Field runs exposed several problematic patterns that required harness-side shims
to even execute a smoke turn. These are "bad agentic designs" to avoid:

| Pattern | Why it's bad | What we did |
|---|---|---|
| Absolute writes at import (e.g., to `/root`) | Fails in locked-down CI/local sandboxes; side effects during import prevent any execution | Set `HOME`, `TMPDIR`, `XDG_CACHE_HOME` to per-agent `.cache`; quarantined agents that still write to absolute paths |
| Gateway-bound imports (require API keys at import) | Prevents offline/testability; introduces secrets into field layers | Provided dummy env vars for local tier to keep import alive; quarantined gateway-only repos for cloud tiers |
| Hard-coded model names/providers (`ChatOpenAI()` at module scope) | Incompatible with local endpoints (OMLX/Qwen), causes 404s | Patched `ChatOpenAI.__init__` before import; added `EVALFORCE_FORCE_MODEL=1` |
| Typed StateGraph with no chat/message surface | Harness scenarios use chat-style inputs; typed graphs expect domain state | Authored thin `evalforge_wrapper.py` modules to translate chat-state ↔ typed-state |
| No runnable Agent builder (no `run_sync`) | Harness expects a callable agent surface | Created minimal local wrappers exposing `build_agent(...)->Agent` with `.run_sync()` |
| Local judge verdict shape mismatch (lists instead of objects) | Strict JSON-object parsing rejects usable scores from local models | Made parsing tolerant of one-element numeric/dict lists; clamp scores to [0,1] |

### 1.2 Model mismatch: agents hardcode gpt-3.5-turbo, OMLX serves Qwen

Real LangGraph agents create `ChatOpenAI()` at module scope with default
model `gpt-3.5-turbo`. Pointing `OPENAI_BASE_URL` at OMLX is not enough —
OMLX only serves local models (`Qwen3.5-9B-MLX-4bit`), so the request 404s.

**Fix:** The field worker monkeypatches `ChatOpenAI.__init__` before the agent
module is imported. Pydantic v2 field-default patching does **not** work —
the `__init__` override is the only reliable approach. The patch must run
**before** the agent module is imported, not after.

Key env vars set before importing agent code:
- `OPENAI_API_KEY=omlx-test`
- `OPENAI_BASE_URL=http://127.0.0.1:8000/v1`
- `EVALFORGE_FIELD_MODEL=Qwen3.5-9B-MLX-4bit`

### 1.3 Don't fight databases — classify agents by infra needs

The harness wasted hours trying to make DB-backed agents runnable (env vars,
fake connection strings, import-time patches). That's the wrong approach.

Importing `my_agent` triggers `create_async_engine(DATABASE_URL)`,
`FAISS.load_local(...)`, `getpass.getpass()`, etc. at module scope. The
harness should **not** try to patch around an agent's boostrap.

Classify agents by what their import-time side effects require:
- **no infra** → local tier (pure Python, importable, callable)
- **needs DB/keys/files** → Docker tier with provisioned infra
- **needs a running server** → out of scope for import-based adapters

Mark it, skip it in the local tier, move on.

### 1.4 Recommendations to agent authors

- Avoid filesystem side effects at import (guard with `if __name__ == "__main__":`)
- Parameterize model/provider/base_url; do not hard-code vendor IDs
- Keep a small, message-friendly entry point for testing, even if production uses typed state
- Do not require secrets or network at import; lazy-initialize
- Prefer relative, sandboxed writes under app-controlled cache dirs

---

## 2. Harness Design & Product Boundaries

### 2.1 Field tests vs normal runs

Early in the project we confused these. Clarification:

| Dimension | Field tests (`field/`) | Product runs (`.evalforge/`) |
|---|---|---|
| Purpose | Adapter wiring, artifact capture, deterministic scorers | Real evaluation, regression, release gating |
| Judge | `MockJudge` (fixed score 0.85) | Real model via `--judge` or `evalforge.toml` |
| How to run | `bash field/run-local.sh --tier local` | `evalforge run --pack ... --agent ... --judge ...` |
| Output | `field/results/` | `.evalforge/runs/`, baselines, comparisons |

**Symptoms we saw:** MockJudge leaking into product runs, producing spurious
WARNs (metrics stuck at 0.85). Field results being treated as product evidence.

**Guardrails:**
- `MockJudge` is scoped to `field/test_field_agent.py` only
- Product runs: `evalforge run ... --judge openai:gpt-4o-mini`
- Code search for `MockJudge(` should return only `field/test_field_agent.py`

### 2.2 Real agents reveal bugs mocks never find

The field harness was not in the original plan — it was added ad hoc. It turned
out to be the only test layer that catches integration reality:

- **Per-agent dependencies matter** — real agents transitively import things
  like `ffmpeg`. The harness must install each agent's deps into the right env.
- **Python version skew** — harness might be 3.11, agent's `uv sync` creates
  3.12 venv. You cannot merge `site-packages` from different Python versions.
- **Nested repos break naive setup** — `uv sync` at repo root is silent no-op
  when `pyproject.toml` is in a subdir.
- **Scenario packs must come from agent config** — don't run every pack for
  every agent.

**Lesson:** Unit/mock coverage is necessary but not sufficient. Plan for a
real-agent field layer from the start.

### 2.3 Field runner bugs we fixed

Running a single agent surfaced two runner bugs:

1. **All scenario packs ran, not the agent's own pack.** Fix: read
   `scenario_packs` from `field/config/<slug>.json`; fall back to all if empty.
2. **Agent dependencies never installed.** Fix: run `setup_commands` via
   `bash -c` inside `field/agents/<slug>`; add agent's `.venv` to `PYTHONPATH`.

**Gotchas:**
- `setup_commands` are command strings, not argv arrays — use `bash -c` for
  word-splitting
- `uv sync` at repo root is no-op when project is nested — target the subdir

### 2.4 Non-fixable local cases (quarantine policy)

| Case | Status | Policy |
|---|---|---|
| Absolute path writes at import (`/root/…`) | Not fixable in harness | Mark `quarantined: true` for local; containerized tiers only |
| Gateway-bound agents (key + base URL required) | Not fixable offline | Quarantine local; cloud tiers with CI secrets only |

---

## 3. Platform & Tooling Issues

### 3.1 Docker isolation on macOS

Docker tests run in a Linux container with mounted host socket. macOS forced:

- **Linux-only platform guard** — tests default to skip on non-Linux. Force
  with `EVALFORGE_DOCKER_ALLOW_DARWIN=1`.
- **`buildx --platform linux/amd64`** — plain `docker build` on macOS produces
  arm64 images that fail under Linux test path.
- **docker-ce-cli inside image** — installs official Docker CE CLI (GPG-keyring
  dance) so tests reach host daemon through mounted socket.
- **HTML-only artifacts** — `--html=... --self-contained-html` produces single
  report; cleanup removes everything except `report.html`.
- **Skip guards** — tests skip (not fail) when Docker CLI/daemon is unavailable.

### 3.2 macOS bash is 3.2

`${2,,}` (bash 4+ lowercase expansion) fails with "bad substitution". Use
`echo "$x" | tr '[:upper:]' '[:lower:]'` instead.

### 3.3 pytest plugin pitfalls

- `pytest_plugins` in non-top-level conftest rejected by pytest 9 — load
  plugin explicitly: `uv run pytest -p evalforge.pytest_plugin ...`
- Runner must target a test file — invoking `pytest` without path collects
  every `test_*.py` in the repo.

### 3.4 Adapter config gotchas

- `Adapter.run(scenario, config)` needs the **full agent config**, not a fresh
  `{"run_id": ...}` dict — `python_import` adapter reads `config["module"]`.
- Real GitHub agents do NOT share a uniform entry point. Each needs per-repo
  adapter config (`field/config/<slug>.json`).
- `gen-field-json.py` is heuristic — some repos need manual config.

---

## 4. Agent Sourcing Strategy

### 4.1 Star-band tier system

We split the agent roster into confidence tiers by GitHub stars (as proxy for
maintenance maturity):

| Tier | Threshold | Agent type |
|---|---|---|
| High | >= 1000 stars | Battle-tested, widely adopted |
| Medium | 100–999 stars | Established but less proven |
| Low | < 50 stars | Young/experimental; stretch batches |

PydanticAI exception: high band relaxed to >= 420 stars (ecosystem is younger).

Round 1 = 30 agents (15 LangGraph + 15 PydanticAI), spread across bands.

### 4.2 Sourcing results

150+ GitHub repos searched. Key filtering: small-to-mid repos, tool-calling
agents, no database dependencies, clear entry points. Large repos (>3 MB),
platforms, frameworks, and database-bound agents rejected.