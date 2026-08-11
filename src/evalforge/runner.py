"""Runner: load packs, run scenarios through adapters, save artifacts.

The Runner is the library-level entry point for an eval run: load a scenario
pack, filter scenarios (optionally by tags), invoke the configured agent via
its adapter for each scenario, and persist the results under
``.evalforge/runs/<run_id>/``:

- ``run.json`` — a run index: run id, pack metadata + hash, sanitized agent
  config, selected tag filter, scenario ids in execution order, and the
  artifact file paths.
- ``artifacts/<scenario_id>.json`` — one normalized RunArtifact per scenario.

Run ids are human-sortable (``run-YYYYMMDD-HHMMSS-<rand>``) so runs order
chronologically on disk and in listings.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evalforge.adapters.base import _sanitize_agent
from evalforge.adapters.factory import create_adapter
from evalforge.loading.pack_loader import load_pack
from evalforge.models.artifact import RunArtifact, TrajectoryStep
from evalforge.models.manifest import build_manifest
from evalforge.models.pack import ScenarioPack
from evalforge.models.trace import compute_trace_diff
from evalforge.observability.metrics import EvalMetrics, MetricsCollector

logger = logging.getLogger("evalforge.runner")

SCENARIO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_scenario_id(scenario_id: str) -> None:
    """Validate scenario_id for safe use in file paths.

    Allowed characters: A-Z, a-z, 0-9, underscore, hyphen.
    This is intentionally strict to prevent path traversal.
    If broader IDs are needed (e.g., dots, colons), update this regex
    and ensure downstream path handling remains safe.
    """
    if not SCENARIO_ID_PATTERN.match(scenario_id):
        raise ValueError(f"invalid scenario_id: {scenario_id!r}")


def generate_run_id() -> str:
    """Generate a human-sortable run id: run-YYYYMMDD-HHMMSS-<rand>."""
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"run-{stamp}-{secrets.token_hex(3)}"


def _pack_hash(path: Path) -> str:
    """Short content hash of the pack file, recorded in the run index."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _now_ms() -> int:
    """Current time as a Unix epoch timestamp in milliseconds."""
    return int(time.time() * 1000)


class Runner:
    """Runs scenario packs against an agent via the configured adapter."""

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
        self._collector = MetricsCollector()

    def load_pack(self, path: str | Path) -> ScenarioPack:
        """Parse and validate a pack; store it for subsequent runs."""
        self._pack = load_pack(path)
        path = Path(path)
        self._pack_path = path
        self._pack_hash_value = _pack_hash(path)
        return self._pack

    @property
    def pack(self) -> ScenarioPack:
        """The currently loaded pack (requires :meth:`load_pack` first)."""
        if self._pack is None:
            raise RuntimeError("load_pack must be called before accessing pack")
        return self._pack

    @property
    def metrics(self) -> EvalMetrics:
        """Collected evaluation metrics from the last run."""
        return self._collector.collect()

    def run_one(self, scenario_id: str, run_id: str | None = None) -> RunArtifact:
        """Run a single scenario and return its artifact (not saved)."""
        pack = self.pack
        scenario = next((s for s in pack.scenarios if s.id == scenario_id), None)
        if scenario is None:
            raise ValueError(f"unknown scenario id: {scenario_id}")
        rid = run_id or generate_run_id()
        config = {**self.agent_config, "run_id": rid}
        artifact = self.adapter.run(scenario, config)
        trace_diff = compute_trace_diff(
            artifact_has_trajectory=bool(artifact.trajectory),
            artifact_status=artifact.status,
            trajectory_len=len(artifact.trajectory),
        )
        if trace_diff is not None:
            artifact = artifact.model_copy(update={"trace_diff": trace_diff})
        if config.get("fixtures"):
            artifact = self._annotate_fixture_usage(artifact, config)
        return artifact

    def _annotate_fixture_usage(
        self, artifact: RunArtifact, config: dict[str, Any]
    ) -> RunArtifact:
        """Add ``fixture_used`` note steps for each consumed fixture.

        Scans the artifact's trajectory for ``tool_call`` steps whose tool
        name matches an available fixture file and appends a ``note`` step
        for each match.
        """
        try:
            from evalforge.fixtures import ToolStub

            stub = ToolStub(
                fixtures_dir=config.get("fixtures_dir", "scenarios/fixtures")
            )
            available = stub.available_tools()
            consumed: set[str] = set()
            for step in artifact.trajectory:
                if step.type == "tool_call" and step.tool in available:
                    consumed.add(step.tool)
            if consumed:
                extra_steps = [
                    TrajectoryStep(type="note", content=f"fixture_used: {t}")
                    for t in sorted(consumed)
                ]
                artifact = artifact.model_copy(
                    update={
                        "trajectory": list(artifact.trajectory) + extra_steps
                    }
                )
        except Exception:
            logger.warning(
                "failed to annotate fixture usage", exc_info=True
            )
        return artifact

    def run_all(
        self,
        tags: list[str] | None = None,
        run_id: str | None = None,
        workers: int = 1,
        max_outstanding: int | None = None,
        emit_manifest: bool = True,
    ) -> list[RunArtifact]:
        """Run all scenarios (optionally filtered by tags) and save results."""
        pack = self.pack
        scenarios = pack.scenarios
        if tags:
            tag_set = set(tags)
            scenarios = [s for s in scenarios if tag_set.intersection(s.tags)]
        rid = run_id or generate_run_id()
        start_iso = _now_iso()
        start_ms = _now_ms()

        self._collector.start_run()

        logger.info("Running %d scenarios with %d workers", len(scenarios), workers)

        if workers <= 1:
            artifacts = []
            for s in scenarios:
                t0 = _now_ms()
                try:
                    artifact = self.run_one(s.id, run_id=rid)
                    duration_ms = _now_ms() - t0
                    status = artifact.status
                    cost = artifact.cost.cost_usd if artifact.cost else 0.0
                    self._collector.record_scenario(
                        s.id, 1.0 if status == "completed" else 0.0, float(duration_ms), status
                    )
                    if cost > 0:
                        self._collector.record_llm_call(
                            self.agent_config.get("type", "unknown"),
                            self.agent_config.get("model", "unknown"),
                            0,
                            cost,
                            float(duration_ms),
                        )
                    artifacts.append(artifact)
                except Exception:
                    self._collector.record_scenario(
                        s.id, 0.0, float(_now_ms() - t0), "error"
                    )
                    raise
        else:
            artifacts = self._run_parallel(scenarios, rid, workers, max_outstanding)
            for artifact in artifacts:
                status = artifact.status
                duration = float(artifact.timestamp.duration_ms if artifact.timestamp else 0)
                cost = artifact.cost.cost_usd if artifact.cost else 0.0
                self._collector.record_scenario(
                    artifact.scenario_id,
                    1.0 if status == "completed" else 0.0,
                    duration,
                    status,
                )
                if cost > 0:
                    self._collector.record_llm_call(
                        self.agent_config.get("type", "unknown"),
                        self.agent_config.get("model", "unknown"),
                        0,
                        cost,
                        duration,
                    )

        self._save_run(
            rid, artifacts, pack, scenarios, tags, start_iso, start_ms,
            emit_manifest=emit_manifest,
        )
        return artifacts

    def _run_parallel(
        self,
        scenarios: list[Any],
        run_id: str,
        workers: int,
        max_outstanding: int | None = None,
    ) -> list[RunArtifact]:
        """Run scenarios in parallel using a thread pool with optional backpressure."""
        artifacts: list[RunArtifact] = []

        def _run_one(s: Any) -> RunArtifact:
            return self.run_one(s.id, run_id=run_id)

        if max_outstanding:
            futures_set: set[Any] = set()
            idx = 0
            with ThreadPoolExecutor(max_workers=workers) as executor:
                while idx < len(scenarios) or futures_set:
                    while idx < len(scenarios) and (
                        not max_outstanding or len(futures_set) < max_outstanding
                    ):
                        futures_set.add(executor.submit(_run_one, scenarios[idx]))
                        idx += 1
                    if not futures_set:
                        break
                    done, futures_set = wait(futures_set, return_when=FIRST_COMPLETED)
                    for future in done:
                        try:
                            artifact = future.result()
                            artifacts.append(artifact)
                        except Exception as exc:
                            from evalforge.models.artifact import (
                                Cost,
                                RunArtifact,
                                RunOutput,
                                RunTimestamps,
                            )
                            artifacts.append(
                                RunArtifact(
                                    id=f"{run_id}-error",
                                    scenario_id="unknown",
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
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(_run_one, s): s for s in scenarios}
                for future in as_completed(futures):
                    try:
                        artifact = future.result()
                        artifacts.append(artifact)
                    except Exception as exc:
                        from evalforge.models.artifact import (
                            Cost,
                            RunArtifact,
                            RunOutput,
                            RunTimestamps,
                        )

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

        scenario_order = {s.id: i for i, s in enumerate(scenarios)}
        artifacts.sort(key=lambda a: scenario_order.get(a.scenario_id, 9999))
        return artifacts

    def _save_run(
        self,
        run_id: str,
        artifacts: list[RunArtifact],
        pack: ScenarioPack,
        scenarios: list[Any],
        tags: list[str] | None,
        start_iso: str,
        start_ms: int,
        emit_manifest: bool = True,
    ) -> None:
        run_dir = self.output_dir / "runs" / run_id
        artifacts_dir = run_dir / "artifacts"
        if (run_dir / "run.json").exists():
            raise ValueError(f"run already exists: {run_id}")
        for s in scenarios:
            _validate_scenario_id(s.id)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        for artifact in artifacts:
            _validate_scenario_id(artifact.scenario_id)
            artifact_path = artifacts_dir / f"{artifact.scenario_id}.json"
            artifact_path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")

        index = {
            "run_id": run_id,
            "pack": {
                "name": pack.pack.name,
                "version": pack.pack.version,
                "description": pack.pack.description,
                "min_evalforge": pack.pack.min_evalforge,
            },
            "trust": pack.pack.trust,
            "pack_hash": self._pack_hash_value,
            "agent": _sanitize_agent(self.agent_config),
            "selected_tags": tags,
            "timestamps": {
                "start": start_iso,
                "end": _now_iso(),
                "duration_ms": _now_ms() - start_ms,
            },
            "scenario_ids": [s.id for s in scenarios],
            "artifacts": {a.scenario_id: f"artifacts/{a.scenario_id}.json" for a in artifacts},
        }
        (run_dir / "run.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

        if emit_manifest:
            tool_call_count = sum(
                sum(1 for s in a.trajectory if s.type == "tool_call")
                for a in artifacts
            )
            manifest = build_manifest(
                run_id=run_id,
                agent_config=_sanitize_agent(self.agent_config),
                execution={
                    "duration_ms": _now_ms() - start_ms,
                    "tool_call_count": tool_call_count,
                    "scenario_count": len(artifacts),
                },
            )
            (run_dir / "run-manifest.json").write_text(
                manifest.model_dump_json(indent=2), encoding="utf-8"
            )
