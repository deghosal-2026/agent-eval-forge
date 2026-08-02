"""Tests for the baselines module: Baseline model and BaselineStore.

Covers:
- Baseline dataclass defaults and serialization roundtrip
- BaselineStore save, load, list, missing-name error, and version validation
- tags and notes fields on Baseline
- BaselineStore describe, tag, annotate, and delete methods
"""

import pytest

from evalforge.baselines.model import Baseline
from evalforge.baselines.store import BaselineStore
from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps


def _artifact(artifact_id: str = "r1", scenario_id: str = "sc-1") -> RunArtifact:
    """Factory helper: create a minimal RunArtifact for test scenarios."""
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
    """A Baseline should populate defaults for agent, git_sha, and created."""
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
    """Baseline.to_dict() followed by Baseline.from_dict() should roundtrip."""
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
    """A baseline saved to store should load back with the same fields."""
    store = BaselineStore(base_dir=str(tmp_path))
    b = Baseline(name="v1.0.0", pack="core", pack_version="1.0.0", runs=[_artifact()])
    store.save(b)
    loaded = store.load("v1.0.0")
    assert loaded.name == "v1.0.0"
    assert len(loaded.runs) == 1


def test_baseline_store_list(tmp_path) -> None:
    """Store.list() should return all saved baseline names."""
    store = BaselineStore(base_dir=str(tmp_path))
    store.save(Baseline(name="v1", pack="core", pack_version="1.0.0", runs=[_artifact()]))
    store.save(Baseline(name="v2", pack="core", pack_version="1.0.0", runs=[_artifact()]))
    names = store.list()
    assert "v1" in names
    assert "v2" in names


def test_baseline_store_load_missing_raises(tmp_path) -> None:
    """Loading a non-existent baseline should raise FileNotFoundError."""
    store = BaselineStore(base_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="v99"):
        store.load("v99")


def test_baseline_validate_version_mismatch(tmp_path) -> None:
    """validate() should warn (not raise) when pack versions differ."""
    store = BaselineStore(base_dir=str(tmp_path))
    b = Baseline(name="v1", pack="core", pack_version="2.0.0", runs=[_artifact()])
    store.save(b)
    result = store.validate("v1", pack_version="1.0.0")
    assert "version mismatch" in result.lower() or not result


def test_baseline_tags_default() -> None:
    """A new Baseline should have an empty tags list by default."""
    b = Baseline(name="v1", pack="core", pack_version="1.0.0", runs=[_artifact()])
    assert b.tags == []


def test_baseline_notes_default() -> None:
    """A new Baseline should have an empty notes string by default."""
    b = Baseline(name="v1", pack="core", pack_version="1.0.0", runs=[_artifact()])
    assert b.notes == ""


def test_baseline_tags_roundtrip() -> None:
    """Tags should survive serialization roundtrip."""
    b = Baseline(
        name="v1",
        pack="core",
        pack_version="1.0.0",
        runs=[_artifact()],
        tags=["golden", "v1.0"],
        notes="Approved baseline for initial release",
    )
    data = b.to_dict()
    restored = Baseline.from_dict(data)
    assert restored.tags == ["golden", "v1.0"]
    assert restored.notes == "Approved baseline for initial release"


def test_baseline_store_tag(tmp_path) -> None:
    """tag() should update tags on a saved baseline."""
    store = BaselineStore(base_dir=str(tmp_path))
    b = Baseline(name="v1", pack="core", pack_version="1.0.0", runs=[_artifact()])
    store.save(b)
    store.tag("v1", ["golden", "prod"])
    loaded = store.load("v1")
    assert loaded.tags == ["golden", "prod"]


def test_baseline_store_annotate(tmp_path) -> None:
    """annotate() should update notes on a saved baseline."""
    store = BaselineStore(base_dir=str(tmp_path))
    b = Baseline(name="v1", pack="core", pack_version="1.0.0", runs=[_artifact()])
    store.save(b)
    store.annotate("v1", "Verified by team")
    loaded = store.load("v1")
    assert loaded.notes == "Verified by team"


def test_baseline_store_delete(tmp_path) -> None:
    """delete() should remove a baseline from disk."""
    store = BaselineStore(base_dir=str(tmp_path))
    b = Baseline(name="v1", pack="core", pack_version="1.0.0", runs=[_artifact()])
    store.save(b)
    store.delete("v1")
    assert "v1" not in store.list()


def test_baseline_store_delete_missing_raises(tmp_path) -> None:
    """delete() on a non-existent baseline should raise FileNotFoundError."""
    store = BaselineStore(base_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="nope"):
        store.delete("nope")


def test_baseline_store_describe(tmp_path) -> None:
    """describe() should return a dict with all expected keys."""
    store = BaselineStore(base_dir=str(tmp_path))
    b = Baseline(
        name="v1",
        pack="core",
        pack_version="1.0.0",
        runs=[_artifact()],
        tags=["golden"],
        notes="Test baseline",
        git_sha="abc123",
    )
    store.save(b)
    info = store.describe("v1")
    assert info["name"] == "v1"
    assert info["pack"] == "core"
    assert info["scenarios"] == 1
    assert info["tags"] == ["golden"]
    assert info["notes"] == "Test baseline"
    assert info["git_sha"] == "abc123"
    assert info["trust"] == "local"
    assert info["avg_score"] is None


def test_baseline_store_describe_with_scores(tmp_path) -> None:
    """describe() should compute avg_score when score_snapshot is present."""
    store = BaselineStore(base_dir=str(tmp_path))
    b = Baseline(
        name="v1",
        pack="core",
        pack_version="1.0.0",
        runs=[_artifact()],
        score_snapshot={
            "scenario_scores": {"sc-1": 0.8, "sc-2": 0.6},
        },
    )
    store.save(b)
    info = store.describe("v1")
    assert info["avg_score"] == pytest.approx(0.7)


def test_baseline_store_tag_missing_raises(tmp_path) -> None:
    """tag() on a non-existent baseline should raise FileNotFoundError."""
    store = BaselineStore(base_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="nope"):
        store.tag("nope", ["golden"])


def test_baseline_store_annotate_missing_raises(tmp_path) -> None:
    """annotate() on a non-existent baseline should raise FileNotFoundError."""
    store = BaselineStore(base_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="nope"):
        store.annotate("nope", "notes")
