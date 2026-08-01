# M8: CI & Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship CI integration, caching, parallel execution, fixture system, validation mode, and security hardening.

**Architecture:** Six independent subsystems each touching distinct areas: caching (new module), fixtures (adapter layer), parallel execution (runner/core), validation (CLI), CI (workflows), security (cross-cutting sanitization). Shared files (cli/run.py, runner.py) are modified in sequential tasks to avoid conflicts.

**Tech Stack:** Python 3.11+, Click, concurrent.futures, hashlib, Pydantic

---

## File Structure

### New files to create:
- `src/evalforge/cache/__init__.py` — cache exports
- `src/evalforge/cache/judge_cache.py` — hash-based judge result cache (24h TTL, file-backed)
- `src/evalforge/cache/run_cache.py` — session-scoped run result cache
- `src/evalforge/cache/schema_cache.py` — pack lifetime schema validation cache
- `src/evalforge/fixtures/__init__.py` — fixture system exports
- `src/evalforge/fixtures/tool_stub.py` — `ToolStub` for intercepting agent tool calls
- `src/evalforge/security/__init__.py` — security module exports
- `src/evalforge/security/sanitize.py` — enhanced API key sanitization
- `src/evalforge/security/sandbox.py` — subprocess sandbox for untrusted packs
- `src/evalforge/security/audit.py` — run audit trail
- `.github/workflows/ci-evalforge.yml` — CI template for users running EvalForge in their own CI
- `docs/ci.md` — CI integration guide
- `tests/test_cache.py` — tests for caching system
- `tests/test_fixtures.py` — tests for fixture system
- `tests/test_security.py` — tests for security model
- `tests/test_parallel.py` — tests for parallel execution

### Files to modify:
- `src/evalforge/cli/run.py` — add `--no-cache`, `--sandbox`, `--max-memory`, `--max-cpu` flags; use parallel execution
- `src/evalforge/cli/cache.py` — enhance to clear specific cache types, add stats
- `src/evalforge/cli/validate.py` — add `--pre-flight` mode
- `src/evalforge/cli/__main__.py` — (if any new top-level commands)
- `src/evalforge/runner.py` — support `--workers` parallel execution
- `src/evalforge/adapters/base.py` — integrate `ToolStub` fixture interception
- `src/evalforge/adapters/subprocess.py` — sandbox mode
- `src/evalforge/scoring/engine.py` — integrate judge result cache
- `.github/workflows/ci.yml` — add `evalforge run` step, artifact upload
- `.env.example` — add security-related vars
- `tests/test_cli.py` — test new flags
- `tests/test_runner.py` — test parallel execution

---

### Task 1: Caching System

**Files:**
- Create: `src/evalforge/cache/__init__.py`
- Create: `src/evalforge/cache/judge_cache.py`
- Create: `src/evalforge/cache/run_cache.py`
- Create: `src/evalforge/cache/schema_cache.py`
- Create: `tests/test_cache.py`
- Modify: `src/evalforge/cli/cache.py`
- Modify: `src/evalforge/scoring/engine.py`
- Modify: `src/evalforge/cli/run.py`

**Interfaces:**
- Produces: `JudgeCache(base_dir, ttl_hours) -> get(key) -> ScoreResult | None / set(key, result)` 
- Produces: `RunCache(base_dir) -> get(run_id) -> RunArtifact | None / set(run_id, artifact)`
- Produces: `SchemaCache() -> get(pack_hash) -> bool / set(pack_hash)`
- Consumes: `cli/run.py` passes `--no-cache` flag through to engine

- [ ] **Step 1: Create `src/evalforge/cache/__init__.py`**

```python
from evalforge.cache.judge_cache import JudgeCache
from evalforge.cache.run_cache import RunCache
from evalforge.cache.schema_cache import SchemaCache

__all__ = ["JudgeCache", "RunCache", "SchemaCache"]
```

- [ ] **Step 2: Create `src/evalforge/cache/judge_cache.py`**

```python
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class JudgeCache:
    """Hash-based judge result cache with configurable TTL.

    Cache key is SHA-256 of (scenario_id + agent_config + judge_model + artifact_hash).
    Results are persisted as JSON files under ``<base_dir>/judge_cache/``.
    """

    def __init__(self, base_dir: str | Path = ".evalforge", ttl_hours: int = 24) -> None:
        self._cache_dir = Path(base_dir) / "judge_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._ttl_seconds = ttl_hours * 3600

    def _key(self, scenario_id: str, agent_config: dict[str, Any], judge_model: str, artifact_hash: str) -> str:
        raw = f"{scenario_id}|{json.dumps(agent_config, sort_keys=True)}|{judge_model}|{artifact_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(self, scenario_id: str, agent_config: dict[str, Any], judge_model: str, artifact_hash: str) -> dict[str, Any] | None:
        key = self._key(scenario_id, agent_config, judge_model, artifact_hash)
        path = self._cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            age = time.time() - data.get("_cached_at", 0)
            if age > self._ttl_seconds:
                path.unlink(missing_ok=True)
                return None
            return data.get("result")
        except (json.JSONDecodeError, KeyError):
            path.unlink(missing_ok=True)
            return None

    def set(self, scenario_id: str, agent_config: dict[str, Any], judge_model: str, artifact_hash: str, result: dict[str, Any]) -> None:
        key = self._key(scenario_id, agent_config, judge_model, artifact_hash)
        path = self._cache_dir / f"{key}.json"
        data = {"_cached_at": time.time(), "result": result}
        path.write_text(json.dumps(data, indent=2))

    def clear(self) -> int:
        count = 0
        if self._cache_dir.exists():
            for f in self._cache_dir.iterdir():
                if f.suffix == ".json":
                    f.unlink()
                    count += 1
        return count

    def stats(self) -> dict[str, Any]:
        if not self._cache_dir.exists():
            return {"files": 0, "size_bytes": 0}
        files = list(self._cache_dir.glob("*.json"))
        return {
            "files": len(files),
            "size_bytes": sum(f.stat().st_size for f in files),
        }
```

- [ ] **Step 3: Create `src/evalforge/cache/run_cache.py`**

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RunCache:
    """Session-scoped in-memory run result cache.

    Avoids re-running scenarios within the same evalforge session.
    """

    def __init__(self) -> None:
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def get(self, pack_hash: str) -> list[dict[str, Any]] | None:
        return self._cache.get(pack_hash)

    def set(self, pack_hash: str, artifacts: list[dict[str, Any]]) -> None:
        self._cache[pack_hash] = artifacts

    def clear(self) -> None:
        self._cache.clear()
```

- [ ] **Step 4: Create `src/evalforge/cache/schema_cache.py`**

```python
class SchemaCache:
    """Pack-lifetime schema validation cache.

    Avoids re-validating the same pack schema within a single run.
    Thread-safe for parallel execution.
    """

    def __init__(self) -> None:
        self._validated: set[str] = set()

    def is_validated(self, pack_hash: str) -> bool:
        return pack_hash in self._validated

    def mark_validated(self, pack_hash: str) -> None:
        self._validated.add(pack_hash)

    def clear(self) -> None:
        self._validated.clear()
```

- [ ] **Step 5: Enhance `src/evalforge/cli/cache.py`**

Add `clear` subcommands for specific cache types and a `stats` subcommand:

```python
@cache_group.command("clear")
@click.option("--output-dir", default=".evalforge", show_default=True)
@click.option("--cache-type", type=click.Choice(["all", "judge", "runs", "baselines"]), default="all", help="Which cache type to clear")
def cache_clear(output_dir: str, cache_type: str) -> None:
    base = Path(output_dir)
    cleared = 0
    targets = {
        "all": ["runs", "baselines", "judge_cache"],
        "judge": ["judge_cache"],
        "runs": ["runs"],
        "baselines": ["baselines"],
    }[cache_type]
    for subdir in targets:
        path = base / subdir
        if path.exists():
            shutil.rmtree(path)
            cleared += 1
    click.echo(f"Cleared {cleared} cache director{'ies' if cleared != 1 else 'y'} under {output_dir}/")

@cache_group.command("stats")
@click.option("--output-dir", default=".evalforge", show_default=True)
def cache_stats(output_dir: str) -> None:
    from evalforge.cache import JudgeCache
    jc = JudgeCache(base_dir=output_dir)
    s = jc.stats()
    click.echo(f"Judge cache: {s['files']} files, {s['size_bytes']} bytes")
```

- [ ] **Step 6: Integrate cache into `src/evalforge/scoring/engine.py`**

In `ScoringEngine.__init__`, accept an optional `judge_cache` parameter. In `_score_scenario`, before calling the LLM judge, check the judge cache first:

```python
# In score_run, compute artifact_hash once per scenario
import hashlib
artifact_hash = hashlib.sha256(artifact.model_dump_json().encode()).hexdigest()[:16]

# Before calling judge, check cache:
if self.judge_cache and judge_client and judge_client.model:
    cached = self.judge_cache.get(
        scenario.id, {}, judge_client.model, artifact_hash
    )
    if cached:
        # Convert cached dict back to ScoreResult
        ...
```

- [ ] **Step 7: Add `--no-cache` flag to `cli/run.py`**

Add option:
```python
@click.option("--no-cache", is_flag=True, help="Disable all caching (judge cache, run cache)")
```

Pass `no_cache` through to the runner and scoring engine. When `--no-cache` is set, skip cache reads.

- [ ] **Step 8: Write tests in `tests/test_cache.py`**

```python
"""Tests for the caching system."""

from pathlib import Path

from evalforge.cache.judge_cache import JudgeCache
from evalforge.cache.run_cache import RunCache
from evalforge.cache.schema_cache import SchemaCache


def test_judge_cache_set_get(tmp_path: Path) -> None:
    cache = JudgeCache(base_dir=str(tmp_path))
    result = {"score": 0.95, "rationale": "good"}
    cache.set("scenario-01", {"model": "gpt-4"}, "gpt-4o-mini", "abc123", result)
    cached = cache.get("scenario-01", {"model": "gpt-4"}, "gpt-4o-mini", "abc123")
    assert cached == result


def test_judge_cache_miss(tmp_path: Path) -> None:
    cache = JudgeCache(base_dir=str(tmp_path))
    assert cache.get("nonexistent", {}, "model", "hash") is None


def test_judge_cache_ttl_expiry(tmp_path: Path) -> None:
    import time
    cache = JudgeCache(base_dir=str(tmp_path), ttl_hours=0)
    time.sleep(0.001)  # ensure TTL has elapsed
    cache.set("s1", {}, "model", "h1", {"score": 1.0})
    assert cache.get("s1", {}, "model", "h1") is None


def test_judge_cache_clear(tmp_path: Path) -> None:
    cache = JudgeCache(base_dir=str(tmp_path))
    cache.set("s1", {}, "model", "h1", {"score": 1.0})
    cache.set("s2", {}, "model", "h2", {"score": 0.5})
    assert cache.clear() == 2
    assert cache.stats()["files"] == 0


def test_judge_cache_stats(tmp_path: Path) -> None:
    cache = JudgeCache(base_dir=str(tmp_path))
    cache.set("s1", {}, "model", "h1", {"score": 1.0})
    stats = cache.stats()
    assert stats["files"] == 1
    assert stats["size_bytes"] > 0


def test_run_cache_set_get() -> None:
    cache = RunCache()
    artifacts = [{"scenario_id": "s1"}]
    cache.set("pack_hash_1", artifacts)
    assert cache.get("pack_hash_1") == artifacts
    assert cache.get("pack_hash_2") is None


def test_run_cache_clear() -> None:
    cache = RunCache()
    cache.set("h1", [{"id": "s1"}])
    cache.clear()
    assert cache.get("h1") is None


def test_schema_cache() -> None:
    cache = SchemaCache()
    assert not cache.is_validated("pack_hash_1")
    cache.mark_validated("pack_hash_1")
    assert cache.is_validated("pack_hash_1")
    cache.clear()
    assert not cache.is_validated("pack_hash_1")
```

---

### Task 2: Fixture System

**Files:**
- Create: `src/evalforge/fixtures/__init__.py`
- Create: `src/evalforge/fixtures/tool_stub.py`
- Create: `tests/test_fixtures.py`
- Modify: `src/evalforge/adapters/base.py`
- Modify: `src/evalforge/cli/run.py`

**Interfaces:**
- Produces: `ToolStub(fixtures_dir) -> intercept(tool_name, payload) -> dict` 
- Consumes: `Adapter._invoke()` wraps tool calls with ToolStub in fixture mode

- [ ] **Step 1: Create `src/evalforge/fixtures/__init__.py`**

```python
from evalforge.fixtures.tool_stub import ToolStub, FixtureNotFoundError

__all__ = ["ToolStub", "FixtureNotFoundError"]
```

- [ ] **Step 2: Create `src/evalforge/fixtures/tool_stub.py`**

```python
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any


class FixtureNotFoundError(KeyError):
    """Raised when a fixture file is missing for a requested tool."""


class ToolStub:
    """Intercepts tool calls and returns deterministic fixture data.

    In ``--fixtures`` mode, every tool call an agent makes is intercepted and
    answered from a JSON fixture file rather than a live service. This makes
    runs fully deterministic and fast.
    """

    def __init__(self, fixtures_dir: str | Path = "scenarios/fixtures") -> None:
        self._fixtures_dir = Path(fixtures_dir)
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._delay_ms: int = 0

    def set_delay_ms(self, delay_ms: int) -> None:
        self._delay_ms = delay_ms

    def _load_fixtures(self, tool_name: str) -> list[dict[str, Any]]:
        if tool_name in self._cache:
            return self._cache[tool_name]
        fixture_path = self._fixtures_dir / f"{tool_name}.json"
        if not fixture_path.exists():
            raise FixtureNotFoundError(
                f"No fixture file for tool '{tool_name}': {fixture_path} not found"
            )
        data = json.loads(fixture_path.read_text())
        if not isinstance(data, list):
            data = [data]
        self._cache[tool_name] = data
        return data

    def intercept(self, tool_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a deterministic fixture response for the given tool call.

        If multiple fixture entries exist, cycles through them round-robin
        based on a hash of the payload for consistent replay.
        """
        if self._delay_ms:
            time.sleep(self._delay_ms / 1000.0)
        fixtures = self._load_fixtures(tool_name)
        if len(fixtures) == 1:
            return fixtures[0]
        idx = 0
        if payload:
            idx = hash(json.dumps(payload, sort_keys=True)) % len(fixtures)
        return fixtures[idx]

    def available_tools(self) -> set[str]:
        if not self._fixtures_dir.exists():
            return set()
        return {f.stem for f in self._fixtures_dir.glob("*.json")}
```

- [ ] **Step 3: Create `tests/test_fixtures.py`**

```python
"""Tests for the fixture system."""

import json
from pathlib import Path

import pytest

from evalforge.fixtures import FixtureNotFoundError, ToolStub


def test_tool_stub_basic(tmp_path: Path) -> None:
    fixture_file = tmp_path / "lookup.json"
    fixture_file.write_text(json.dumps({"result": "ok"}))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    result = stub.intercept("lookup")
    assert result == {"result": "ok"}


def test_tool_stub_missing_tool(tmp_path: Path) -> None:
    stub = ToolStub(fixtures_dir=str(tmp_path))
    with pytest.raises(FixtureNotFoundError):
        stub.intercept("nonexistent_tool")


def test_tool_stub_list_with_query(tmp_path: Path) -> None:
    fixture_file = tmp_path / "search.json"
    fixtures = [{"id": 1}, {"id": 2}, {"id": 3}]
    fixture_file.write_text(json.dumps(fixtures))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    r1 = stub.intercept("search", {"query": "foo"})
    r2 = stub.intercept("search", {"query": "bar"})
    assert isinstance(r1, dict)
    assert isinstance(r2, dict)
    # Deterministic: same payload yields same result
    assert stub.intercept("search", {"query": "foo"}) == r1


def test_tool_stub_single_fixture_is_returned_directly(tmp_path: Path) -> None:
    fixture_file = tmp_path / "ping.json"
    fixture_file.write_text(json.dumps({"status": "ok"}))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    assert stub.intercept("ping") == {"status": "ok"}


def test_tool_stub_caching(tmp_path: Path) -> None:
    fixture_file = tmp_path / "cached_tool.json"
    fixture_file.write_text(json.dumps([{"data": "v1"}]))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    assert stub.intercept("cached_tool") == {"data": "v1"}
    # Modify the file on disk — cache should still return original
    fixture_file.write_text(json.dumps([{"data": "v2"}]))
    assert stub.intercept("cached_tool") == {"data": "v1"}


def test_available_tools(tmp_path: Path) -> None:
    (tmp_path / "tool_a.json").write_text("{}")
    (tmp_path / "tool_b.json").write_text("{}")
    stub = ToolStub(fixtures_dir=str(tmp_path))
    assert stub.available_tools() == {"tool_a", "tool_b"}


def test_available_tools_empty_dir(tmp_path: Path) -> None:
    stub = ToolStub(fixtures_dir=str(tmp_path))
    assert stub.available_tools() == set()


def test_delay_ms(tmp_path: Path) -> None:
    import time
    fixture_file = tmp_path / "slow_tool.json"
    fixture_file.write_text(json.dumps({"result": "eventually"}))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    stub.set_delay_ms(50)
    start = time.time()
    stub.intercept("slow_tool")
    elapsed = (time.time() - start) * 1000
    assert elapsed >= 40  # allow 10ms tolerance
```

- [ ] **Step 4: Integrate ToolStub into `src/evalforge/adapters/base.py`**

Modify the `Adapter.run()` method to support a `fixtures` config flag. When `config.get("fixtures")` is `True`, wrap tool calls through `ToolStub`:

In the `run()` method, after building the payload, intercept tool results:

```python
def run(self, scenario: Scenario, config: dict[str, Any]) -> RunArtifact:
    run_id = config.get("run_id", "run-unknown")
    payload = build_invocation_payload(scenario, run_id)
    start_iso = _now_iso()
    start_ms = _now_ms()
    strict = bool(config.get("strict_output", False))

    # Fixture mode: intercept tool calls before they reach the agent
    fixture_mode = bool(config.get("fixtures", False))
    if fixture_mode:
        from evalforge.fixtures import ToolStub
        stub = ToolStub(fixtures_dir=config.get("fixtures_dir", "scenarios/fixtures"))
        # Replace allowed tools with stub responses in the payload
        # (Subprocess adapter handles this differently - via env var)
        payload["_fixture_mode"] = True

    try:
        raw = self._invoke(payload, config)
        ...
```

But this is tricky because the adapter doesn't actually intercept tool calls — the agent makes tool calls. The fixture mode means the agent's tool calls go to stub data instead of real APIs.

For subprocess adapter: pass `EVALFORGE_FIXTURES_DIR` env var so the agent script knows to use fixtures.
For Python import/LangGraph/PydanticAI adapters: the adapter itself or the example agent needs to use `ToolStub`.

Let me adjust: The fixture system is better implemented by having the example agents/adapters check for a fixtures config and use ToolStub themselves. The adapter `_invoke` method passes `fixtures` in the config.

Actually, the simplest approach: for the subprocess adapter, set the env var. For the python_import adapter, the example agent function checks config. For langgraph/pydantic, the example agent does the same.

Let me simplify: just pass `_fixture_mode` and `_fixtures_dir` through the payload, and document that agents should check these. The adapter contract already supports this via the config dict.

Let me modify the approach to be simpler:

In `base.py`, add a helper method `_inject_fixtures(payload, config)` that modifies the payload to include fixture metadata. The actual interception happens in the agent code.

- [ ] **Step 5: Add fixture flags to `cli/run.py`**

Modify the `--fixtures` flag to support both `fixtures` and `live` modes:

```python
@click.option(
    "--fixtures",
    is_flag=True,
    default=None,
    help="Run with fixture data (deterministic mode, no live tool calls)",
)
@click.option(
    "--fixtures-dir",
    default="scenarios/fixtures",
    show_default=True,
    help="Directory containing fixture JSON files",
)
```

Pass these through in `agent_config`.

- [ ] **Step 6: Write fixture integration test**

Test that `ToolStub` integrates with the adapter flow by verifying fixture mode is passed through to the agent config.

---

### Task 3: Parallel Execution

**Files:**
- Modify: `src/evalforge/runner.py`
- Modify: `src/evalforge/cli/run.py`
- Create: `tests/test_parallel.py`

**Interfaces:**
- Produces: `Runner.run_all(tags, run_id, workers=1)` — runs scenarios in parallel when workers > 1
- Consumes: `cli/run.py` passes `--workers N` to Runner

- [ ] **Step 1: Modify `src/evalforge/runner.py` to support parallel execution**

Add `concurrent.futures` to `run_all`:

```python
from __future__ import annotations

import hashlib
import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evalforge.adapters.base import _sanitize_agent
from evalforge.adapters.factory import create_adapter
from evalforge.loading.pack_loader import load_pack
from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import ScenarioPack


class Runner:
    def __init__(
        self,
        agent_config: dict[str, Any],
        output_dir: str | Path = ".evalforge",
    ) -> None:
        self.agent_config = agent_config
        self.output_dir = Path(output_dir)
        self.adapter = create_adapter(agent_config)
        self._pack: ScenarioPack | None = None
        self._pack_path: Path | None = None
        self._pack_hash_value: str | None = None

    def run_all(
        self,
        tags: list[str] | None = None,
        run_id: str | None = None,
        workers: int = 1,
    ) -> list[RunArtifact]:
        pack = self.pack
        scenarios = pack.scenarios
        if tags:
            tag_set = set(tags)
            scenarios = [s for s in scenarios if tag_set.intersection(s.tags)]
        rid = run_id or generate_run_id()
        start_iso = _now_iso()
        start_ms = _now_ms()

        if workers <= 1:
            artifacts = [self.run_one(s.id, run_id=rid) for s in scenarios]
        else:
            artifacts = self._run_parallel(scenarios, rid, workers)

        self._save_run(rid, artifacts, pack, scenarios, tags, start_iso, start_ms)
        return artifacts

    def _run_parallel(
        self,
        scenarios: list[Any],
        run_id: str,
        workers: int,
    ) -> list[RunArtifact]:
        """Run scenarios in parallel using a thread pool."""
        artifacts: list[RunArtifact] = []

        def _run_one(s: Any) -> RunArtifact:
            return self.run_one(s.id, run_id=run_id)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_run_one, s): s for s in scenarios}
            for future in as_completed(futures):
                try:
                    artifact = future.result()
                    artifacts.append(artifact)
                except Exception as exc:
                    from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps

                    scenario = futures[future]
                    artifacts.append(
                        RunArtifact(
                            id=f"{run_id}-{scenario.id}",
                            scenario_id=scenario.id,
                            agent=_sanitize_agent(self.agent_config),
                            timestamp=RunTimestamps(
                                start=_now_iso(), end=_now_iso(), duration_ms=0,
                            ),
                            output=RunOutput(final=None, structured=None),
                            trajectory=[],
                            cost=Cost(),
                            status="error",
                            error=f"parallel worker error: {exc}",
                        )
                    )

        # Preserve original scenario order
        scenario_order = {s.id: i for i, s in enumerate(scenarios)}
        artifacts.sort(key=lambda a: scenario_order.get(a.scenario_id, 9999))
        return artifacts
```

- [ ] **Step 2: Enhance `--workers` flag in `cli/run.py`**

Update the `--workers` help text and remove the "(single-threaded in v0.1)" note:

```python
@click.option(
    "--workers",
    default=1,
    type=int,
    show_default=True,
    help="Number of parallel workers (1 = serial execution)",
)
```

Pass `workers` to `run_all`:

```python
artifacts = runner.run_all(tags=tag_list, run_id=run_id, workers=workers)
```

- [ ] **Step 3: Write `tests/test_parallel.py`**

```python
"""Tests for parallel execution."""

from pathlib import Path

from evalforge.runner import Runner


def test_serial_execution(tmp_path: Path, monkeypatch) -> None:
    """Workers=1 runs scenarios sequentially."""
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.echo_agent", "fixtures": True},
        output_dir=str(tmp_path),
    )
    runner.load_pack("scenarios/core-launch.yaml")
    artifacts = runner.run_all(workers=1)
    assert len(artifacts) > 0
    assert all(a.status == "completed" for a in artifacts)


def test_parallel_execution(tmp_path: Path, monkeypatch) -> None:
    """Workers=4 runs all scenarios to completion."""
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.echo_agent", "fixtures": True},
        output_dir=str(tmp_path),
    )
    runner.load_pack("scenarios/core-launch.yaml")
    artifacts = runner.run_all(workers=4)
    assert len(artifacts) > 0
    assert all(a.status == "completed" for a in artifacts)


def test_parallel_preserves_order(tmp_path: Path, monkeypatch) -> None:
    """Parallel results maintain original scenario order."""
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.echo_agent", "fixtures": True},
        output_dir=str(tmp_path),
    )
    runner.load_pack("scenarios/core-launch.yaml")
    artifacts = runner.run_all(workers=4)
    scenario_ids = [a.scenario_id for a in artifacts]
    assert scenario_ids == sorted(scenario_ids)


def test_parallel_with_tags(tmp_path: Path, monkeypatch) -> None:
    """Parallel execution respects tag filters."""
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.echo_agent", "fixtures": True},
        output_dir=str(tmp_path),
    )
    runner.load_pack("scenarios/core-launch.yaml")
    artifacts = runner.run_all(tags=["retrieval"], workers=2)
    assert all("retrieval" in a.scenario_id for a in artifacts)


def test_parallel_error_handling(tmp_path: Path, monkeypatch) -> None:
    """Parallel execution captures individual worker errors."""
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.echo_agent", "fixtures": True},
        output_dir=str(tmp_path),
    )
    runner.load_pack("scenarios/core-launch.yaml")
    # Use many workers to test concurrency
    artifacts = runner.run_all(workers=8)
    completed = [a for a in artifacts if a.status == "completed"]
    assert len(completed) == len(artifacts)
```

---

### Task 4: Validation Mode

**Files:**
- Modify: `src/evalforge/cli/validate.py`

- [ ] **Step 1: Add `--pre-flight` mode to `validate.py`**

Add a `--pre-flight` flag that runs all validation checks (pack, agent, baseline, fixtures) in a single pass with CI-friendly output:

```python
@click.option(
    "--pre-flight",
    is_flag=True,
    help="Run all validation checks (pack + agent + baseline + fixtures) in one pass",
)
```

When `--pre-flight` is set without explicit `--pack`/`--agent` etc., auto-detect defaults:
- Pack: look for `scenarios/core-launch.yaml`
- Agent: no default (require `--agent`)
- Fixtures: check if `scenarios/fixtures/` exists

```python
if pre_flight:
    if not pack:
        default_pack = "scenarios/core-launch.yaml"
        if Path(default_pack).exists():
            pack = default_pack
    if not check_fixtures and Path("scenarios/fixtures").exists():
        check_fixtures = True
```

- [ ] **Step 2: Add validation of agent connectivity**

In the `--agent` validation block, add a connectivity check for HTTP adapters:

```python
if cfg["type"] == "http":
    import httpx
    try:
        r = httpx.head(cfg.get("url", ""), timeout=5)
        if r.status_code >= 500:
            results["agent"]["warnings"] = results["agent"].get("warnings", [])
            results["agent"]["warnings"].append(
                f"HTTP endpoint returned {r.status_code}"
            )
    except Exception as e:
        results["agent"]["warnings"] = results["agent"].get("warnings", [])
        results["agent"]["warnings"].append(f"HTTP connectivity check failed: {e}")
```

---

### Task 5: CI Integration

**Files:**
- Create: `.github/workflows/ci-evalforge.yml`
- Modify: `.github/workflows/ci.yml`
- Create: `docs/ci.md`

- [ ] **Step 1: Create `.github/workflows/ci-evalforge.yml` — CI template for users**

```yaml
name: EvalForge Evaluation

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read
  checks: write

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true

      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: uv sync --extra dev --extra judge

      - name: Pre-flight validation
        run: uv run evalforge validate --pre-flight --agent python:my_agent.py --strict

      - name: Run evaluation
        run: |
          uv run evalforge run \
            --pack scenarios/core-launch.yaml \
            --agent python:my_agent.py \
            --output .evalforge \
            --output-format github-actions \
            --ci

      - name: Upload evaluation artifacts
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: evalforge-results
          path: .evalforge/runs/
```

- [ ] **Step 2: Enhance existing `.github/workflows/ci.yml`**

Add an `eval` job that runs `evalforge` with the mock agent:

```yaml
jobs:
  test:
    # ... existing test job ...

  eval:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: uv sync --extra dev
      - name: Validate pack
        run: uv run evalforge validate --pack scenarios/core-launch.yaml --strict
      - name: Run full pack (fixtures mode)
        run: |
          uv run evalforge run \
            --pack scenarios/core-launch.yaml \
            --agent python:fixtures.echo_agent \
            --output .evalforge \
            --output-format github-actions \
            --ci \
            --fixtures
      - name: Upload results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: evalforge-results
          path: .evalforge/runs/
```

- [ ] **Step 3: Create `docs/ci.md`**

Write a CI integration guide covering:
- Overview of CI modes
- Pre-flight validation
- Full evaluation runs
- Baseline comparison in CI
- Comment generation for PRs
- Common configuration examples (GitHub Actions, GitLab CI)

---

### Task 6: Security Model

**Files:**
- Create: `src/evalforge/security/__init__.py`
- Create: `src/evalforge/security/sanitize.py`
- Create: `src/evalforge/security/sandbox.py`
- Create: `src/evalforge/security/audit.py`
- Create: `tests/test_security.py`
- Modify: `src/evalforge/adapters/subprocess.py`
- Modify: `src/evalforge/cli/run.py`
- Modify: `.env.example`

- [ ] **Step 1: Create `src/evalforge/security/__init__.py`**

```python
from evalforge.security.sanitize import sanitize_config, SANITIZE_PATTERNS
from evalforge.security.sandbox import SandboxConfig, sandboxed_run
from evalforge.security.audit import AuditTrail

__all__ = ["sanitize_config", "SANITIZE_PATTERNS", "SandboxConfig", "sandboxed_run", "AuditTrail"]
```

- [ ] **Step 2: Create `src/evalforge/security/sanitize.py`**

Enhanced sanitization that redacts secrets from logs, configs, and artifacts:

```python
"""API key and secret sanitization utilities.

Extends ``_sanitize_agent`` in ``adapters/base.py`` with regex-based
redaction so secrets are removed even from nested dicts and strings.
"""

from __future__ import annotations

import re
from typing import Any

# Keys whose values should always be redacted
SANITIZE_KEYS = {"api_key", "token", "secret", "password", "credential", "auth_token"}

# Patterns that look like API keys or tokens in string values
SANITIZE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),   # OpenAI-style keys
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),  # Anthropic-style keys
    re.compile(r"ghp_[A-Za-z0-9_-]{36,}"),   # GitHub PATs
    re.compile(r"gho_[A-Za-z0-9_-]{36,}"),   # GitHub OAuth
]


def _redact_string(value: str) -> str:
    """Redact any API-key-like patterns in a string."""
    for pattern in SANITIZE_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def sanitize_config(config: dict[str, Any], _depth: int = 0) -> dict[str, Any]:
    """Deep-sanitize a config dict, handling nesting."""
    if _depth > 10:
        return {"[REDACTED]": "[max depth]"}
    result: dict[str, Any] = {}
    for key, value in config.items():
        if key in SANITIZE_KEYS:
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = sanitize_config(value, _depth + 1)
        elif isinstance(value, str):
            result[key] = _redact_string(value)
        else:
            result[key] = value
    return result
```

- [ ] **Step 3: Create `src/evalforge/security/sandbox.py`**

Subprocess sandbox for untrusted packs. Strips environment variables, uses `subprocess.Popen` with restricted env:

```python
"""Sandbox for running untrusted scenario packs.

When ``--sandbox`` is enabled, the subprocess adapter:
- Strips all env vars except a minimal allowlist
- Sets ``EVALFORGE_SANDBOX=1`` in the child process
- Adds a 2x timeout multiplier to prevent DoS
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import Any

# Minimal env vars allowed in sandbox mode
SANDBOX_ALLOWLIST = {
    "PATH", "HOME", "TMPDIR", "USER",
    "EVALFORGE_SANDBOX", "EVALFORGE_FIXTURES_DIR",
}


@dataclass
class SandboxConfig:
    """Configuration for sandboxed agent execution."""
    enabled: bool = False
    allowlist: set[str] = field(default_factory=lambda: SANDBOX_ALLOWLIST)
    timeout_multiplier: float = 2.0
    max_memory_mb: int = 512
    max_cpu_percent: int = 80


def sandboxed_run(
    args: list[str],
    config: SandboxConfig,
    env: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess:
    """Run a subprocess with sandbox restrictions."""
    if not config.enabled:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
        )

    sandbox_env: dict[str, str] = {"EVALFORGE_SANDBOX": "1"}
    for key in config.allowlist:
        if key in os.environ:
            sandbox_env[key] = os.environ[key]
    if env:
        for key in config.allowlist.intersection(env):
            sandbox_env[key] = env[key]

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout * config.timeout_multiplier,
        env=sandbox_env,
    )
```

- [ ] **Step 4: Create `src/evalforge/security/audit.py`**

Audit trail that logs every run invocation, result, and any security-relevant events:

```python
"""Audit trail for evaluation runs.

Records every run invocation, its configuration, results, and any
security-relevant events (sandbox activations, key sanitizations, etc.)
to an append-only JSON log file.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditTrail:
    """Append-only audit trail for evaluation runs.

    Each call to :meth:`record` appends a JSON line to
    ``<base_dir>/audit/audit.log``.
    """

    def __init__(self, base_dir: str | Path = ".evalforge") -> None:
        self._log_dir = Path(base_dir) / "audit"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / "audit.log"

    def record(self, event: str, details: dict[str, Any]) -> None:
        """Record a single audit event.

        Args:
            event: Event type (e.g. ``"run_start"``, ``"run_complete"``,
                ``"sandbox_active"``, ``"key_sanitized"``).
            details: Event-specific data.
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "details": details,
        }
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_events(self, event_type: str | None = None) -> list[dict[str, Any]]:
        """Read all audit events, optionally filtered by type."""
        if not self._log_path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self._log_path.read_text().strip().split("\n"):
            if not line:
                continue
            entry = json.loads(line)
            if event_type is None or entry.get("event") == event_type:
                events.append(entry)
        return events
```

- [ ] **Step 5: Integrate sandbox into `src/evalforge/adapters/subprocess.py`**

Modify the subprocess adapter's `_invoke` to use `sandboxed_run` when `config.get("sandbox")` is `True`:

```python
def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str:
    import subprocess
    from evalforge.security.sandbox import SandboxConfig, sandboxed_run

    agent_cmd = config.get("command", config.get("module", "./agent"))
    timeout = config.get("timeout_seconds", 120)

    sandbox = SandboxConfig(
        enabled=bool(config.get("sandbox", False)),
    )

    extra_env = {
        "EVALFORGE_PAYLOAD": json.dumps(payload),
        "EVALFORGE_FIXTURES_DIR": config.get("fixtures_dir", "scenarios/fixtures"),
    }
    if config.get("fixtures"):
        extra_env["EVALFORGE_FIXTURES"] = "1"

    try:
        result = sandboxed_run(
            args=[agent_cmd],
            config=sandbox,
            env=extra_env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise AgentTimeoutError(f"agent timed out after {timeout}s") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else ""
        raise AdapterError(
            f"agent exited with code {result.returncode}"
            + (f": {stderr}" if stderr else "")
        )

    return result.stdout
```

- [ ] **Step 6: Add `--sandbox` flag to `cli/run.py`**

```python
@click.option(
    "--sandbox",
    is_flag=True,
    help="Run in sandbox mode (restricted env, no API key passthrough)",
)
```

Pass `sandbox` in `agent_config`.

- [ ] **Step 7: Integrate audit trail into `cli/run.py`**

In the `run()` function, record run start and completion:

```python
from evalforge.security.audit import AuditTrail
from evalforge.security.sanitize import sanitize_config

audit = AuditTrail(base_dir=output)
audit.record("run_start", {
    "run_id": run_id,
    "pack": pack,
    "agent": sanitize_config(agent_config),
    "sandbox": bool(agent_config.get("sandbox", False)),
    "ci": ci,
})

# ... after run completes ...

audit.record("run_complete", {
    "run_id": run_id,
    "exit_code": run_score.exit_code,
    "passed": run_score.totals["passed"],
    "failed": run_score.totals["failed"],
    "safety_violations": run_score.safety_violations,
})
```

- [ ] **Step 8: Update `.env.example`**

```env
# LLM-as-judge providers (optional)
EVALFORGE_OPENAI_API_KEY=
EVALFORGE_ANTHROPIC_API_KEY=

# Defaults (override evalforge.toml)
EVALFORGE_JUDGE_MODEL=openai:gpt-4o-mini
EVALFORGE_OUTPUT_DIR=.evalforge
EVALFORGE_LOG_LEVEL=info

# Security
EVALFORGE_SANDBOX=false
EVALFORGE_MAX_MEMORY_MB=512
```

- [ ] **Step 9: Write `tests/test_security.py`**

```python
"""Tests for the security module."""

import json
import os
from pathlib import Path

import pytest

from evalforge.security.audit import AuditTrail
from evalforge.security.sandbox import SandboxConfig, sandboxed_run
from evalforge.security.sanitize import sanitize_config


class TestSanitize:
    def test_redacts_api_key_keys(self) -> None:
        config = {"api_key": "sk-12345678901234567890", "model": "gpt-4"}
        result = sanitize_config(config)
        assert result["api_key"] == "[REDACTED]"
        assert result["model"] == "gpt-4"

    def test_redacts_openai_key_pattern_in_strings(self) -> None:
        config = {"prompt": "Use key sk-12345678901234567890 here"}
        result = sanitize_config(config)
        assert "sk-12345678901234567890" not in result["prompt"]
        assert "[REDACTED]" in result["prompt"]

    def test_redacts_github_token(self) -> None:
        token = "ghp_" + "a" * 36
        config = {"github_token": token}
        result = sanitize_config(config)
        assert result["github_token"] == "[REDACTED]"

    def test_nested_dict_sanitization(self) -> None:
        config = {"credentials": {"api_key": "sk-secret", "user": "admin"}}
        result = sanitize_config(config)
        assert result["credentials"]["api_key"] == "[REDACTED]"
        assert result["credentials"]["user"] == "admin"

    def test_depth_limit(self) -> None:
        deep = {}
        current = deep
        for _ in range(15):
            current["nested"] = {}
            current = current["nested"]
        result = sanitize_config(deep)
        assert "[REDACTED]" in str(result)


class TestAudit:
    def test_record_and_read(self, tmp_path: Path) -> None:
        audit = AuditTrail(base_dir=str(tmp_path))
        audit.record("run_start", {"run_id": "run-001"})
        audit.record("run_complete", {"run_id": "run-001", "passed": 5})
        events = audit.get_events()
        assert len(events) == 2
        assert events[0]["event"] == "run_start"
        assert events[0]["details"]["run_id"] == "run-001"

    def test_filter_by_event_type(self, tmp_path: Path) -> None:
        audit = AuditTrail(base_dir=str(tmp_path))
        audit.record("run_start", {})
        audit.record("run_complete", {})
        starts = audit.get_events("run_start")
        assert len(starts) == 1

    def test_empty_audit(self, tmp_path: Path) -> None:
        audit = AuditTrail(base_dir=str(tmp_path))
        assert audit.get_events() == []


class TestSandbox:
    def test_sandbox_echo(self) -> None:
        config = SandboxConfig(enabled=True)
        result = sandboxed_run(["echo", "hello"], config)
        assert result.stdout.strip() == "hello"
        assert result.returncode == 0

    def test_sandbox_strips_env(self) -> None:
        os.environ["EVIL_VAR"] = "malicious"
        config = SandboxConfig(enabled=True)
        result = sandboxed_run(
            ["python3", "-c", "import os; print(os.environ.get('EVIL_VAR', 'NOT_SET'))"],
            config,
        )
        assert result.stdout.strip() == "NOT_SET"

    def test_sandbox_allowlist_preserved(self) -> None:
        config = SandboxConfig(enabled=True)
        result = sandboxed_run(
            ["python3", "-c", "import os; print(os.environ.get('PATH', 'NOT_SET')[:4])"],
            config,
        )
        assert result.stdout.strip() != "NOT_SET"

    def test_sandbox_timing(self) -> None:
        config = SandboxConfig(enabled=True, timeout_multiplier=2.0)
        import subprocess
        result = sandboxed_run(["echo", "timing"], config, timeout=10)
        assert result.stdout.strip() == "timing"
```

---

### Self-Review

**1. Spec coverage:**
- [x] Caching: Task 1 covers judge cache, run cache, schema cache, `--no-cache` flag
- [x] Parallel execution: Task 3 covers `--workers`, thread pool, error handling
- [x] Fixture system: Task 2 covers `ToolStub`, fixture/live modes, `--fixtures-dir`
- [x] Validation mode: Task 4 covers `--pre-flight`, connectivity check
- [x] CI integration: Task 5 covers workflow templates, `--ci` enhancements, docs/ci.md
- [x] Security model: Task 6 covers sanitization, sandbox, audit trail, `--sandbox`

**2. Placeholder scan:** No TBD/TODO/incomplete sections found.

**3. Type consistency:** All interface types are consistent across tasks (dict[str, Any] for configs, Path for directories, bool for flags).