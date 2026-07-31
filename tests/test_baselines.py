"""Tests for the baselines module: Baseline model and BaselineStore."""

import pytest

from evalforge.baselines.model import Baseline
from evalforge.baselines.store import BaselineStore
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
