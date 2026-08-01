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

    def run_one(self, scenario_id: str, run_id: str | None = None) -> RunArtifact:
        """Run a single scenario and return its artifact (not saved)."""
        pack = self.pack
        scenario = next((s for s in pack.scenarios if s.id == scenario_id), None)
        if scenario is None:
            raise ValueError(f"unknown scenario id: {scenario_id}")
        rid = run_id or generate_run_id()
        config = {**self.agent_config, "run_id": rid}
        return self.adapter.run(scenario, config)

    def run_all(
        self,
        tags: list[str] | None = None,
        run_id: str | None = None,
        workers: int = 1,
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
    ) -> None:
        run_dir = self.output_dir / "runs" / run_id
        artifacts_dir = run_dir / "artifacts"
        if (run_dir / "run.json").exists():
            raise ValueError(f"run already exists: {run_id}")
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        for artifact in artifacts:
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
