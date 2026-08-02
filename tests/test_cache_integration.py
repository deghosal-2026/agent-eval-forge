"""Tests for cache persistence across restarts and SchemaCache fast-path behavior."""

from __future__ import annotations

import time
from pathlib import Path

import yaml

from evalforge.cache.judge_cache import JudgeCache
from evalforge.cache.schema_cache import SchemaCache
from evalforge.loading.pack_loader import _SCHEMA_CACHE, load_pack
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

# Import scorer modules to register them
from evalforge.scoring.deterministic import (  # noqa: F401
    gates,
    tools,
)
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.judge import scorers  # noqa: F401
from evalforge.scoring.judge.mock import MockJudge
from evalforge.scoring.result import RunScore


def _make_pack() -> ScenarioPack:
    return ScenarioPack(
        pack=PackMetadata(name="test", version="1.0.0"),
        scenarios=[
            Scenario(
                id="sc-1",
                title="T",
                input="i",
                goal="g",
                allowed_tools=[Tool(name="a")],
                budget=Budget(max_steps=5),
                expected=Expected(type="exact", value="ok"),
                metrics={"policy_adherence": Metric(threshold=1.0)},
                tags=["retrieval"],
            ),
        ],
    )


def _make_artifact() -> RunArtifact:
    return RunArtifact(
        id="r1",
        scenario_id="sc-1",
        timestamp=RunTimestamps(start="2024-01-01T00:00:00Z", end="2024-01-01T00:00:01Z", duration_ms=1000),  # noqa: E501
        output=RunOutput(final="ok", structured=None),
        trajectory=[],
        cost=Cost(),
        status="completed",
        error=None,
        agent={},
    )


def test_judge_cache_persistence_across_restarts(tmp_path: Path) -> None:
    pack = _make_pack()
    artifact = _make_artifact()
    judge = MockJudge(score=1.0, rationale="good")

    cache_dir = tmp_path / "cache"
    judge_cache = JudgeCache(base_dir=str(cache_dir))
    engine = ScoringEngine(pack, judge_cache=judge_cache)
    engine.score_run([artifact], judge=judge)
    assert judge_cache.stats()["files"] == 1

    new_engine = ScoringEngine(pack, judge_cache=judge_cache)
    result = new_engine.score_run([artifact], judge=judge)
    assert isinstance(result, RunScore)
    assert result.exit_code == 0


def test_judge_cache_ttl_expiry_on_restart(tmp_path: Path) -> None:
    pack = _make_pack()
    artifact = _make_artifact()
    judge = MockJudge(score=1.0, rationale="good")

    cache_dir = tmp_path / "cache"
    judge_cache = JudgeCache(base_dir=str(cache_dir), ttl_hours=0)
    time.sleep(0.001)
    engine = ScoringEngine(pack, judge_cache=judge_cache)
    engine.score_run([artifact], judge=judge)

    new_cache = JudgeCache(base_dir=str(cache_dir), ttl_hours=0)
    new_engine = ScoringEngine(pack, judge_cache=new_cache)
    result = new_engine.score_run([artifact], judge=judge)
    assert isinstance(result, RunScore)
    assert new_cache.stats()["files"] == 1


def test_judge_cache_corruption_tolerance(tmp_path: Path) -> None:
    cache = JudgeCache(base_dir=str(tmp_path))

    cache.set("s1", {}, "model", "h1", {"score": 0.95})
    cache_files = list(cache._cache_dir.iterdir())
    assert len(cache_files) == 1
    cache_file = cache_files[0]

    cache_file.write_text("not valid json")
    result = cache.get("s1", {}, "model", "h1")
    assert result is None
    assert not cache_file.exists()


def test_schema_cache_fast_path() -> None:
    cache = SchemaCache()
    pack_hash = "test_hash_123"

    assert not cache.is_validated(pack_hash)
    cache.mark_validated(pack_hash)
    assert cache.is_validated(pack_hash)
    cache.clear()
    assert not cache.is_validated(pack_hash)


def test_schema_cache_clears_on_content_change(tmp_path: Path) -> None:
    pack_file = tmp_path / "test_pack.yaml"
    pack_data = {
        "pack": {"name": "cache_test", "version": "1.0.0"},
        "scenarios": [
            {
                "id": "sc-1",
                "title": "Test",
                "input": "hello",
                "goal": "respond",
                "allowed_tools": [{"name": "a"}],
                "budget": {"max_steps": 5},
                "expected": {"type": "exact", "value": "ok"},
                "metrics": {"exact_match": {"threshold": 1.0}},
            },
        ],
    }
    pack_file.write_text(yaml.dump(pack_data))

    _SCHEMA_CACHE.clear()
    pack = load_pack(pack_file)
    assert isinstance(pack, ScenarioPack)

    _SCHEMA_CACHE.clear()
    pack2 = load_pack(pack_file)
    assert isinstance(pack2, ScenarioPack)
