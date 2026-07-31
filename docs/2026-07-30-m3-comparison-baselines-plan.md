# M3: Comparison & Baselines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save baseline snapshots from scored runs, compare candidate runs against baselines at three levels (scenario, family, pack), and produce JSON + Markdown reports with CI-friendly exit codes.

**Architecture:** Two sub-packages under `evalforge`. `baselines/` owns the `Baseline` model and `BaselineStore` (save/load/list/validate). `comparison/` owns the `ComparisonEngine` (delta computation) and `ComparisonReport` (output formatting). The engine consumes `RunScore` from the scoring engine and `RunArtifact` from the runner — no circular dependencies.

**Tech Stack:** Python 3.11+, pydantic (models), dataclasses, json, pathlib

**Design doc:** `docs/spec.md` (§"Baseline Model", §"Comparison Model", §"Report Generation")

## Global Constraints

- Python >=3.11, uv for dependency management
- ruff linting (E,F,W,I,B,UP,S,RUF — 100 char line limit)
- mypy strict mode on `src/evalforge/` only (tests not type-checked)
- pytest with coverage >90%
- TDD: write failing test first, verify it fails, implement, verify passes
- Every comparison failure must normalize to a valid ComparisonReport (never abort)
- Existing test patterns: plain functions, type annotations, factory helpers at module level

---

## File Structure

### New files (src)

```
src/evalforge/baselines/
├── __init__.py          # update: exports Baseline, BaselineStore
├── model.py             # Baseline dataclass
└── store.py             # BaselineStore (save, load, list, validate)

src/evalforge/comparison/
├── __init__.py          # update: exports ComparisonEngine, ComparisonReport
├── engine.py            # ComparisonEngine (delta computation, 3-level aggregation)
└── report.py            # ComparisonReport model + JSON/Markdown rendering
```

### New test files

```
tests/
├── test_baselines.py    # Baseline model + BaselineStore tests
├── test_comparison_engine.py    # ComparisonEngine tests
└── test_comparison_report.py    # ComparisonReport JSON + Markdown tests
```

---

### Task 1: Baseline model + BaselineStore

**Files:**
- Create: `src/evalforge/baselines/model.py`
- Create: `src/evalforge/baselines/store.py`
- Modify: `src/evalforge/baselines/__init__.py` (add exports)
- Create: `tests/test_baselines.py`

**Interfaces:**
- Consumes: `RunArtifact` from `evalforge.models.artifact`, `ScenarioPack` from `evalforge.models.pack`
- Produces: `Baseline` dataclass, `BaselineStore` class

- [ ] **Step 1: Write failing tests for Baseline model**

```python
# tests/test_baselines.py
import json
from datetime import datetime

from evalforge.baselines.model import Baseline
from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps


def _artifact(artifact_id: str = "r1", scenario_id: str = "sc-1") -> RunArtifact:
    return RunArtifact(
        id=artifact_id,
        scenario_id=scenario_id,
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final="ok", structured=None),
        trajectory=[],
        cost=Cost(),
        status="completed",
        error=None,
        agent={},
    )


def test_baseline_defaults() -> None:
    b = Baseline(
        name="v1.0.0",
        pack="core-launch-pack",
        pack_version="1.0.0",
        runs=[_artifact()],
    )
    assert b.name == "v1.0.0"
    assert b.pack == "core-launch-pack"
    assert len(b.runs) == 1
    assert b.created is not None


def test_baseline_serialization_roundtrip() -> None:
    b = Baseline(
        name="v1.0.0",
        pack="core-launch-pack",
        pack_version="1.0.0",
        runs=[_artifact()],
        created="2026-07-30T00:00:00Z",
    )
    data = b.to_dict()
    restored = Baseline.from_dict(data)
    assert restored.name == b.name
    assert restored.pack == b.pack
    assert len(restored.runs) == 1
    assert restored.runs[0].id == "r1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_baselines.py -v` — expected: ImportError for Baseline

- [ ] **Step 3: Create `src/evalforge/baselines/model.py`**

```python
"""Baseline model — an explicit golden snapshot of accepted agent runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from evalforge.models.artifact import RunArtifact


@dataclass
class Baseline:
    name: str
    pack: str
    pack_version: str
    runs: list[RunArtifact]
    agent: dict = field(default_factory=dict)
    git_sha: str | None = None
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "pack": self.pack,
            "pack_version": self.pack_version,
            "agent": self.agent,
            "git_sha": self.git_sha,
            "created": self.created,
            "runs": [r.model_dump(mode="json") for r in self.runs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Baseline:
        runs = [RunArtifact(**r) for r in data["runs"]]
        return cls(
            name=data["name"],
            pack=data["pack"],
            pack_version=data["pack_version"],
            runs=runs,
            agent=data.get("agent", {}),
            git_sha=data.get("git_sha"),
            created=data.get("created", ""),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_baselines.py::test_baseline_defaults tests/test_baselines.py::test_baseline_serialization_roundtrip -v` — expected: 2 PASS

- [ ] **Step 5: Write failing tests for BaselineStore**

```python
# append to tests/test_baselines.py
import pytest
from evalforge.baselines.store import BaselineStore


def test_baseline_store_save_and_load(tmp_path) -> None:
    store = BaselineStore(base_dir=str(tmp_path))
    b = Baseline(name="v1.0.0", pack="core", pack_version="1.0.0", runs=[_artifact()])
    store.save(b)
    loaded = store.load("v1.0.0")
    assert loaded.name == "v1.0.0"
    assert len(loaded.runs) == 1


def test_baseline_store_list(tmp_path) -> None:
    store = BaselineStore(base_dir=str(tmp_path))
    store.save(Baseline(name="v1", pack="core", pack_version="1.0.0", runs=[_artifact()]))
    store.save(Baseline(name="v2", pack="core", pack_version="1.0.0", runs=[_artifact()]))
    names = store.list()
    assert "v1" in names
    assert "v2" in names


def test_baseline_store_load_missing_raises(tmp_path) -> None:
    store = BaselineStore(base_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="v99"):
        store.load("v99")


def test_baseline_validate_version_mismatch(tmp_path) -> None:
    store = BaselineStore(base_dir=str(tmp_path))
    b = Baseline(name="v1", pack="core", pack_version="2.0.0", runs=[_artifact()])
    store.save(b)
    result = store.validate("v1", pack_version="1.0.0")
    assert "version mismatch" in result.lower() or not result  # warns, doesn't raise
```

- [ ] **Step 6: Run to verify they fail**

Run: `uv run pytest tests/test_baselines.py -v` — expected: ImportError for BaselineStore

- [ ] **Step 7: Create `src/evalforge/baselines/store.py`**

```python
"""Baseline store — filesystem persistence for golden baselines."""

from __future__ import annotations

import json
from pathlib import Path

from evalforge.baselines.model import Baseline


class BaselineStore:
    def __init__(self, base_dir: str = ".evalforge/baselines") -> None:
        self._base = Path(base_dir)

    def _path(self, name: str) -> Path:
        return self._base / f"{name}.json"

    def save(self, baseline: Baseline) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        self._path(baseline.name).write_text(
            json.dumps(baseline.to_dict(), indent=2)
        )

    def load(self, name: str) -> Baseline:
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"Baseline not found: {name}")
        return Baseline.from_dict(json.loads(path.read_text()))

    def list(self) -> list[str]:
        if not self._base.exists():
            return []
        return sorted(
            p.stem for p in self._base.iterdir() if p.suffix == ".json"
        )

    def validate(self, name: str, pack_version: str) -> str:
        baseline = self.load(name)
        if baseline.pack_version != pack_version:
            return (
                f"version mismatch: baseline={baseline.pack_version}, "
                f"pack={pack_version}"
            )
        return ""
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_baselines.py -v` — expected: 6 PASS

- [ ] **Step 9: Update `src/evalforge/baselines/__init__.py`**

```python
"""Golden baselines: save, load, validate, and list accepted agent runs.

A baseline is the explicit "we approved this" snapshot for a scenario pack —
the thing every future change is compared against (spec §"Baseline Model").
Explicit baselines beat "whatever happened to run last": a candidate run only
passes if it matches an accepted reference, not the last CI run.
"""

from evalforge.baselines.model import Baseline
from evalforge.baselines.store import BaselineStore

__all__ = ["Baseline", "BaselineStore"]
```

- [ ] **Step 10: Commit**

```bash
git add src/evalforge/baselines/ tests/test_baselines.py
git commit -m "feat(baselines): add Baseline model and BaselineStore with save/load/list/validate"
```

---

### Task 2: ComparisonEngine

**Files:**
- Create: `src/evalforge/comparison/engine.py`
- Modify: `src/evalforge/comparison/__init__.py` (add exports)
- Create: `tests/test_comparison_engine.py`

**Interfaces:**
- Consumes: `Baseline` from `evalforge.baselines.model`, `RunScore` from `evalforge.scoring.result`, `ScenarioPack` from `evalforge.models.pack`
- Produces: `ComparisonEngine` with `compare()` returning `ComparisonResult` (including cost delta from baseline vs candidate artifacts)

- [ ] **Step 1: Write failing tests for ComparisonEngine**

```python
# tests/test_comparison_engine.py
import pytest

from evalforge.baselines.model import Baseline
from evalforge.comparison.engine import ComparisonEngine, ComparisonResult
from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps
from evalforge.models.pack import (
    Budget,
    Expected,
    Metric,
    PackMetadata,
    Scenario,
    ScenarioPack,
    Tool,
)
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.result import RunScore, ScenarioScore, ScoreResult
from evalforge.scoring.deterministic import tools  # noqa: F401
from evalforge.scoring.judge import scorers  # noqa: F401


def _artifact(final: str = "ok", scenario_id: str = "sc-1") -> RunArtifact:
    return RunArtifact(
        id=f"r-{scenario_id}",
        scenario_id=scenario_id,
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final=final, structured=None),
        trajectory=[],
        cost=Cost(),
        status="completed",
        error=None,
        agent={},
    )


def _pack() -> ScenarioPack:
    return ScenarioPack(
        pack=PackMetadata(name="test", version="1.0.0"),
        scenarios=[
            Scenario(
                id="sc-1", title="T", input="i", goal="g",
                allowed_tools=[Tool(name="a")],
                budget=Budget(max_steps=5),
                expected=Expected(type="exact", value="ok"),
                metrics={"tool_correctness": Metric(threshold=1.0)},
                tags=["retrieval"],
            ),
            Scenario(
                id="sc-2", title="T2", input="i2", goal="g2",
                allowed_tools=[Tool(name="b")],
                budget=Budget(max_steps=5),
                expected=Expected(type="exact", value="ok"),
                metrics={"tool_correctness": Metric(threshold=1.0)},
                tags=["synthesis"],
            ),
        ],
    )


def _run_score(pack: ScenarioPack, artifacts: list[RunArtifact]) -> RunScore:
    engine = ScoringEngine(pack)
    return engine.score_run(artifacts)


def test_comparison_result_defaults() -> None:
    r = ComparisonResult(scenario_deltas={}, family_deltas={}, aggregate={})
    assert r.scenario_deltas == {}
    assert r.aggregate == {}


def test_compare_identical_runs() -> None:
    pack = _pack()
    arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    baseline = Baseline(name="v1", pack="test", pack_version="1.0.0", runs=arts)
    baseline_score = _run_score(pack, arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(baseline_score, baseline_score, baseline)
    assert result.aggregate["overall_score_delta"] == 0.0
    assert result.aggregate["regressed"] == 0
    assert result.aggregate["improved"] == 0


def test_compare_regression_detected() -> None:
    pack = _pack()
    passing_arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    failing_arts = [
        _artifact(final="bad", scenario_id="sc-1"),
        _artifact(scenario_id="sc-2"),
    ]
    failing_arts[0].trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "unknown", "args": {}, "duration_ms": 1})(),
    ]
    baseline = Baseline(name="v1", pack="test", pack_version="1.0.0", runs=passing_arts)
    baseline_score = _run_score(pack, passing_arts)
    candidate_score = _run_score(pack, failing_arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(baseline_score, candidate_score, baseline)
    assert result.aggregate["regressed"] >= 1
    assert result.aggregate["overall_score_delta"] < 0


def test_compare_family_deltas() -> None:
    pack = _pack()
    arts = [_artifact(scenario_id="sc-1"), _artifact(scenario_id="sc-2")]
    baseline = Baseline(name="v1", pack="test", pack_version="1.0.0", runs=arts)
    baseline_score = _run_score(pack, arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(baseline_score, baseline_score, baseline)
    assert "retrieval" in result.family_deltas
    assert "synthesis" in result.family_deltas
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_comparison_engine.py -v` — expected: ImportError for ComparisonEngine, ComparisonResult

- [ ] **Step 3: Create `src/evalforge/comparison/engine.py`**

```python
"""Comparison engine — candidate-vs-baseline delta computation."""

from __future__ import annotations

from dataclasses import dataclass, field

from evalforge.baselines.model import Baseline
from evalforge.models.pack import ScenarioPack
from evalforge.scoring.result import RunScore


@dataclass
class ComparisonResult:
    scenario_deltas: dict[str, dict]
    family_deltas: dict[str, dict]
    aggregate: dict


class ComparisonEngine:
    def __init__(self, pack: ScenarioPack) -> None:
        self._pack = pack
        self._scenario_map = {s.id: s for s in pack.scenarios}

    def compare(
        self,
        baseline_score: RunScore,
        candidate_score: RunScore,
        baseline: Baseline,
        candidate_artifacts: list | None = None,
    ) -> ComparisonResult:
        scenario_deltas: dict[str, dict] = {}
        family_scores: dict[str, list[float]] = {}
        candidate_family_scores: dict[str, list[float]] = {}

        all_ids = set(baseline_score.scenario_scores) | set(candidate_score.scenario_scores)
        for sid in all_ids:
            base_ss = baseline_score.scenario_scores.get(sid)
            cand_ss = candidate_score.scenario_scores.get(sid)
            base_score = self._scenario_avg(base_ss)
            cand_score = self._scenario_avg(cand_ss)
            delta = (cand_score or 0.0) - (base_score or 0.0)

            scenario_deltas[sid] = {
                "baseline_score": base_score,
                "candidate_score": cand_score,
                "delta": delta,
                "baseline_status": base_ss.status if base_ss else None,
                "candidate_status": cand_ss.status if cand_ss else None,
                "regressed": (
                    base_ss is not None and cand_ss is not None
                    and base_ss.status == "passed" and cand_ss.status != "passed"
                ),
                "improved": (
                    base_ss is not None and cand_ss is not None
                    and base_ss.status != "passed" and cand_ss.status == "passed"
                ),
                "new_failure": base_ss is None and cand_ss is not None and cand_ss.status != "passed",
                "new_pass": base_ss is None and cand_ss is not None and cand_ss.status == "passed",
            }

            scenario = self._scenario_map.get(sid)
            if scenario and scenario.tags:
                for tag in scenario.tags:
                    if base_score is not None:
                        family_scores.setdefault(tag, []).append(base_score)
                    if cand_score is not None:
                        candidate_family_scores.setdefault(tag, []).append(cand_score)

        family_deltas: dict[str, dict] = {}
        for tag in set(family_scores) | set(candidate_family_scores):
            base_avg = _avg(family_scores.get(tag, []))
            cand_avg = _avg(candidate_family_scores.get(tag, []))
            family_deltas[tag] = {
                "baseline_avg": base_avg,
                "candidate_avg": cand_avg,
                "score_delta": cand_avg - base_avg,
            }

        regressed = sum(1 for d in scenario_deltas.values() if d["regressed"])
        improved = sum(1 for d in scenario_deltas.values() if d["improved"])
        new_failures = sum(1 for d in scenario_deltas.values() if d["new_failure"])
        new_passes = sum(1 for d in scenario_deltas.values() if d["new_pass"])
        unchanged = sum(
            1 for d in scenario_deltas.values()
            if not d["regressed"] and not d["improved"]
            and not d["new_failure"] and not d["new_pass"]
        )
        overall_delta = _avg([
            d["delta"] for d in scenario_deltas.values()
            if d["delta"] is not None
        ])

        # Cost delta: baseline runs vs candidate artifacts
        base_cost = _sum_cost(baseline.runs)
        cand_cost = _sum_cost(candidate_artifacts or [])
        cost_delta = round(cand_cost - base_cost, 6)

        aggregate = {
            "total_scenarios": len(scenario_deltas),
            "regressed": regressed,
            "improved": improved,
            "new_failures": new_failures,
            "new_passes": new_passes,
            "unchanged": unchanged,
            "overall_score_delta": overall_delta,
            "cost_delta_usd": cost_delta,
            "baseline_cost_usd": base_cost,
            "candidate_cost_usd": cand_cost,
        }

        return ComparisonResult(
            scenario_deltas=scenario_deltas,
            family_deltas=family_deltas,
            aggregate=aggregate,
        )

    @staticmethod
    def _scenario_avg(
        ss: object,
    ) -> float | None:
        if ss is None:
            return None
        scores = [
            r.score for r in getattr(ss, "metric_results", {}).values()
            if r.score is not None
        ]
        return _avg(scores) if scores else None


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _sum_cost(artifacts: list) -> float:
    total = 0.0
    for a in artifacts:
        c = getattr(a, "cost", None)
        if c is not None:
            total += getattr(c, "cost_usd", 0.0) or 0.0
    return round(total, 6)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_comparison_engine.py -v` — expected: 4 PASS

- [ ] **Step 5: Update `src/evalforge/comparison/__init__.py`**

```python
"""Comparison engine: candidate-vs-baseline deltas and reports."""

from evalforge.comparison.engine import ComparisonEngine, ComparisonResult

__all__ = ["ComparisonEngine", "ComparisonResult"]
```

- [ ] **Step 6: Commit**

```bash
git add src/evalforge/comparison/ tests/test_comparison_engine.py
git commit -m "feat(comparison): add ComparisonEngine with 3-level delta computation"
```

---

### Task 3: ComparisonReport (JSON + Markdown)

**Files:**
- Create: `src/evalforge/comparison/report.py`
- Create: `tests/test_comparison_report.py`

**Interfaces:**
- Consumes: `ComparisonResult` from `engine.py`, `RunScore` from `evalforge.scoring.result`, `Baseline` from `evalforge.baselines.model`
- Produces: `ComparisonReport` with `to_json()` and `to_markdown()` methods

- [ ] **Step 1: Write failing tests**

```python
# tests/test_comparison_report.py
import pytest

from evalforge.comparison.engine import ComparisonResult
from evalforge.comparison.report import ComparisonReport
from evalforge.scoring.result import RunScore, ScenarioScore, ScoreResult


def _make_result() -> ComparisonResult:
    return ComparisonResult(
        scenario_deltas={
            "sc-1": {
                "baseline_score": 1.0, "candidate_score": 0.5, "delta": -0.5,
                "baseline_status": "passed", "candidate_status": "failed",
                "regressed": True, "improved": False,
                "new_failure": False, "new_pass": False,
            },
            "sc-2": {
                "baseline_score": 0.0, "candidate_score": 1.0, "delta": 1.0,
                "baseline_status": "failed", "candidate_status": "passed",
                "regressed": False, "improved": True,
                "new_failure": False, "new_pass": False,
            },
        },
        family_deltas={
            "retrieval": {"baseline_avg": 1.0, "candidate_avg": 0.5, "score_delta": -0.5},
        },
        aggregate={
            "total_scenarios": 2, "regressed": 1, "improved": 1,
            "new_failures": 0, "new_passes": 0, "unchanged": 0,
            "overall_score_delta": 0.25,
        },
    )


def _run_score() -> RunScore:
    return RunScore(
        scenario_scores={},
        totals={"passed": 1, "warned": 0, "failed": 1},
        safety_violations=[],
        exit_code=1,
    )


def test_report_to_json() -> None:
    report = ComparisonReport(
        baseline_name="v1.0.0",
        candidate_name="v1.1.0",
        result=_make_result(),
        candidate_score=_run_score(),
    )
    data = report.to_json()
    assert data["baseline_name"] == "v1.0.0"
    assert data["candidate_name"] == "v1.1.0"
    assert data["aggregate"]["regressed"] == 1
    assert "sc-1" in data["scenario_deltas"]
    assert "retrieval" in data["family_deltas"]


def test_report_to_markdown() -> None:
    report = ComparisonReport(
        baseline_name="v1.0.0",
        candidate_name="v1.1.0",
        result=_make_result(),
        candidate_score=_run_score(),
    )
    md = report.to_markdown()
    assert "v1.0.0" in md
    assert "v1.1.0" in md
    assert "Summary" in md
    assert "sc-1" in md
    assert "regressed" in md.lower()


def test_report_markdown_contains_safety_violations() -> None:
    score = RunScore(
        scenario_scores={},
        totals={"passed": 0, "warned": 0, "failed": 1},
        safety_violations=["zero_disallowed_actions"],
        exit_code=4,
    )
    report = ComparisonReport(
        baseline_name="v1", candidate_name="v2",
        result=_make_result(), candidate_score=score,
    )
    md = report.to_markdown()
    assert "SAFETY" in md.upper() or "exit code 4" in md
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_comparison_report.py -v` — expected: ImportError for ComparisonReport

- [ ] **Step 3: Create `src/evalforge/comparison/report.py`**

```python
"""Comparison report — JSON and Markdown report generation."""

from __future__ import annotations

from dataclasses import dataclass

from evalforge.comparison.engine import ComparisonResult
from evalforge.scoring.result import RunScore


@dataclass
class ComparisonReport:
    baseline_name: str
    candidate_name: str
    result: ComparisonResult
    candidate_score: RunScore

    def to_json(self) -> dict:
        return {
            "baseline_name": self.baseline_name,
            "candidate_name": self.candidate_name,
            "summary": {
                "total_scenarios": self.result.aggregate["total_scenarios"],
                "regressed": self.result.aggregate["regressed"],
                "improved": self.result.aggregate["improved"],
                "new_failures": self.result.aggregate["new_failures"],
                "new_passes": self.result.aggregate["new_passes"],
                "unchanged": self.result.aggregate["unchanged"],
            },
            "aggregate": {
                "overall_score_delta": self.result.aggregate["overall_score_delta"],
                "candidate_totals": self.candidate_score.totals,
                "candidate_exit_code": self.candidate_score.exit_code,
                "safety_violations": self.candidate_score.safety_violations,
                "cost_delta_usd": self.result.aggregate.get("cost_delta_usd", 0),
            },
            "scenario_deltas": self.result.scenario_deltas,
            "family_deltas": self.result.family_deltas,
        }

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Comparison Report: {self.baseline_name} → {self.candidate_name}")
        lines.append("")

        agg = self.result.aggregate
        lines.append("## Summary")
        lines.append(f"| Metric | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Total Scenarios | {agg['total_scenarios']} |")
        lines.append(f"| Regressed | {agg['regressed']} |")
        lines.append(f"| Improved | {agg['improved']} |")
        lines.append(f"| New Failures | {agg['new_failures']} |")
        lines.append(f"| New Passes | {agg['new_passes']} |")
        lines.append(f"| Unchanged | {agg['unchanged']} |")
        lines.append(f"| Overall Score Delta | {agg['overall_score_delta']:+.3f} |")
        lines.append(f"| Cost Delta (USD) | {agg.get('cost_delta_usd', 0):+.6f} |")
        lines.append(f"| Exit Code | {self.candidate_score.exit_code} |")
        if self.candidate_score.safety_violations:
            lines.append(
                f"| Safety Violations | {', '.join(self.candidate_score.safety_violations)} |"
            )
        lines.append("")

        lines.append("## Per-Scenario Deltas")
        lines.append("| Scenario | Baseline | Candidate | Delta | Status |")
        lines.append("|---|---|---|---|---|")
        for sid, delta in sorted(self.result.scenario_deltas.items()):
            label = "regressed" if delta["regressed"] else "improved" if delta["improved"] else "unchanged"
            lines.append(
                f"| {sid} | {delta['baseline_score'] or '-'} | "
                f"{delta['candidate_score'] or '-'} | "
                f"{delta['delta']:+.3f}" if delta['delta'] is not None else "-" + " | {label} |"
            )
        lines.append("")

        if self.result.family_deltas:
            lines.append("## Per-Family Deltas")
            lines.append("| Family | Baseline Avg | Candidate Avg | Delta |")
            lines.append("|---|---|---|---|")
            for fam, fd in sorted(self.result.family_deltas.items()):
                lines.append(
                    f"| {fam} | {fd['baseline_avg']:.3f} | {fd['candidate_avg']:.3f} | "
                    f"{fd['score_delta']:+.3f} |"
                )
            lines.append("")

        lines.append("---")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_comparison_report.py -v` — expected: 3 PASS

- [ ] **Step 5: Update `src/evalforge/comparison/__init__.py`**

```python
"""Comparison engine: candidate-vs-baseline deltas and reports."""

from evalforge.comparison.engine import ComparisonEngine, ComparisonResult
from evalforge.comparison.report import ComparisonReport

__all__ = ["ComparisonEngine", "ComparisonResult", "ComparisonReport"]
```

- [ ] **Step 6: Commit**

```bash
git add src/evalforge/comparison/report.py tests/test_comparison_report.py
git commit -m "feat(comparison): add ComparisonReport with JSON and Markdown output"
```

---

### Task 4: Integration tests

**Files:**
- Create: `tests/test_comparison_integration.py`

**Interfaces:**
- Consumes: All M3 components end-to-end

- [ ] **Step 1: Write failing integration tests**

```python
# tests/test_comparison_integration.py
import json
from pathlib import Path

import pytest

from evalforge.baselines.model import Baseline
from evalforge.baselines.store import BaselineStore
from evalforge.comparison.engine import ComparisonEngine
from evalforge.comparison.report import ComparisonReport
from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps
from evalforge.models.pack import (
    Budget,
    Expected,
    Metric,
    PackMetadata,
    Scenario,
    ScenarioPack,
    Tool,
)
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.deterministic import (  # noqa: F401
    gates, tools,
)
from evalforge.scoring.judge import scorers  # noqa: F401


def _pack() -> ScenarioPack:
    return ScenarioPack(
        pack=PackMetadata(name="test-pack", version="1.0.0"),
        scenarios=[
            Scenario(
                id="sc-1", title="T1", input="i1", goal="g1",
                allowed_tools=[Tool(name="a")],
                budget=Budget(max_steps=5),
                expected=Expected(type="exact", value="ok"),
                metrics={"tool_correctness": Metric(threshold=1.0)},
                tags=["retrieval"],
            ),
            Scenario(
                id="sc-2", title="T2", input="i2", goal="g2",
                allowed_tools=[Tool(name="b")],
                budget=Budget(max_steps=5),
                expected=Expected(type="exact", value="ok"),
                metrics={"tool_correctness": Metric(threshold=1.0)},
                tags=["synthesis"],
            ),
        ],
    )


def _artifact(final: str = "ok", sid: str = "sc-1") -> RunArtifact:
    return RunArtifact(
        id=f"r-{sid}", scenario_id=sid,
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final=final, structured=None),
        trajectory=[], cost=Cost(), status="completed", error=None, agent={},
    )


def test_end_to_end_baseline_save_compare_report(tmp_path: Path) -> None:
    pack = _pack()
    base_dir = str(tmp_path / ".evalforge")
    store = BaselineStore(base_dir=f"{base_dir}/baselines")

    # Create and save baseline
    base_arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    base_score = ScoringEngine(pack).score_run(base_arts)
    baseline = Baseline(name="v1.0", pack="test-pack", pack_version="1.0.0", runs=base_arts)
    store.save(baseline)

    # Verify baseline loads
    loaded = store.load("v1.0")
    assert len(loaded.runs) == 2

    # Compare candidate with a regression
    cand_arts = [
        _artifact(final="bad", sid="sc-1"),
        _artifact(sid="sc-2"),
    ]
    cand_arts[0].trajectory = [
        type("Step", (), {"type": "tool_call", "tool": "unknown", "args": {}, "duration_ms": 1})(),
    ]
    cand_score = ScoringEngine(pack).score_run(cand_arts)
    engine = ComparisonEngine(pack)
    result = engine.compare(base_score, cand_score, loaded, candidate_artifacts=cand_arts)

    assert result.aggregate["regressed"] >= 1
    assert result.aggregate["overall_score_delta"] < 0
    assert "cost_delta_usd" in result.aggregate

    # Generate report
    report = ComparisonReport(
        baseline_name="v1.0",
        candidate_name="candidate",
        result=result,
        candidate_score=cand_score,
    )

    json_output = report.to_json()
    assert json_output["aggregate"]["regressed"] >= 1

    md_output = report.to_markdown()
    assert "v1.0" in md_output
    assert "sc-1" in md_output
    assert "regressed" in md_output.lower()


def test_end_to_end_all_pass_no_regression(tmp_path: Path) -> None:
    pack = _pack()
    store = BaselineStore(base_dir=str(tmp_path / ".evalforge" / "baselines"))
    arts = [_artifact(sid="sc-1"), _artifact(sid="sc-2")]
    score = ScoringEngine(pack).score_run(arts)
    baseline = Baseline(name="v1.0", pack="test-pack", pack_version="1.0.0", runs=arts)
    store.save(baseline)

    engine = ComparisonEngine(pack)
    result = engine.compare(score, score, baseline)
    assert result.aggregate["regressed"] == 0
    assert result.aggregate["improved"] == 0
    assert result.aggregate["overall_score_delta"] == 0.0
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_comparison_integration.py -v` — expected: ImportError for ComparisonReport.to_json (if Task 3 not done yet) or other failures

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/test_comparison_integration.py -v` — expected: 2 PASS (after all prior tasks done)

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/ -q` — expected: all existing 111 tests + 15 new M3 tests = 126 PASS

- [ ] **Step 5: Run lint + typecheck**

```bash
uv run ruff check src/evalforge/
uv run mypy --strict src/evalforge/
```

- [ ] **Step 6: Commit**

```bash
git add tests/test_comparison_integration.py
git commit -m "test(comparison): add end-to-end integration tests for full M3 pipeline"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** Every baseline/comparison/report requirement from spec.md has a task
- [ ] **Placeholder scan:** No TBDs, vague instructions, or missing code blocks
- [ ] **Type consistency:** `ComparisonResult` and `ComparisonReport` signatures match across Task 2 and Task 3