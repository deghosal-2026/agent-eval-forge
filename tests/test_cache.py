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
    time.sleep(0.001)
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