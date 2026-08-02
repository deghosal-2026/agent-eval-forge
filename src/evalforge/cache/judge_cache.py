"""File-backed cache for LLM judge results.

Reduces cost and latency by caching judge evaluations keyed by
(scenario_id, agent_config, judge_model, artifact_hash) with configurable TTL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, cast

# Logger for cache operations. Used at DEBUG level for hits (high volume),
# INFO for expirations (low volume, useful in CI), and WARNING for corruptions
# (infrequent but actionable — indicates a bug or filesystem issue).
logger = logging.getLogger("evalforge.cache")


class JudgeCache:
    """File-backed cache for LLM judge evaluation results.

    Each cached result is stored as a separate JSON file named by a SHA-256
    hash of the composite key. Entries expire after a configurable TTL.
    """

    def __init__(self, base_dir: str | Path = ".evalforge", ttl_hours: int = 24) -> None:
        """Initialize a file-backed judge result cache.

        Each cached result is a separate JSON file keyed by a SHA-256 hash of
        the scenario ID, agent config, judge model, and artifact content hash.
        The 24-hour default TTL balances cost savings with staleness — reruns
        within a day reuse cached results, but a full CI matrix run on consecutive
        days will re-evaluate.

        Args:
            base_dir: Root directory for the cache (``<base_dir>/judge_cache/``).
            ttl_hours: Time-to-live in hours for cached entries.
        """
        self._cache_dir = Path(base_dir) / "judge_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._ttl_seconds = ttl_hours * 3600

    def _key(
        self, scenario_id: str, agent_config: dict[str, Any],
        judge_model: str, artifact_hash: str,
    ) -> str:
        """Generate a deterministic cache key from evaluation parameters.

        Combines all inputs into a single string and hashes it with SHA-256,
        truncating to 32 hex characters for brevity.

        Args:
            scenario_id: The scenario identifier.
            agent_config: The agent configuration dict (sorted for consistency).
            judge_model: The judge model name.
            artifact_hash: Hash of the run artifact content.

        Returns:
            A 32-character hexadecimal cache key.
        """
        raw = (
            f"{scenario_id}|{json.dumps(agent_config, sort_keys=True)}"
            f"|{judge_model}|{artifact_hash}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(
        self, scenario_id: str, agent_config: dict[str, Any], judge_model: str, artifact_hash: str
    ) -> dict[str, Any] | None:
        """Retrieve a cached judge result.

        Returns ``None`` if the cache entry is missing, expired, or corrupted.
        Expired entries are automatically deleted.

        Args:
            scenario_id: The scenario identifier.
            agent_config: The agent configuration.
            judge_model: The judge model name.
            artifact_hash: Hash of the run artifact content.

        Returns:
            The cached result dict, or ``None``.
        """
        key = self._key(scenario_id, agent_config, judge_model, artifact_hash)
        path = self._cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                return None
            age = time.time() - data.get("_cached_at", 0)
            if age > self._ttl_seconds:
                path.unlink(missing_ok=True)
                logger.info("Judge cache expired for scenario %s (age=%.0fs)", scenario_id, age)
                return None
            result = data.get("result")
            if isinstance(result, dict):
                logger.debug("Judge cache hit for scenario %s", scenario_id)
                return cast(dict[str, Any], result)
            return None
        except (json.JSONDecodeError, KeyError):
            path.unlink(missing_ok=True)
            logger.warning("Judge cache corrupted for scenario %s, removed", scenario_id)
            return None

    def set(
        self, scenario_id: str, agent_config: dict[str, Any], judge_model: str,
        artifact_hash: str, result: dict[str, Any],
    ) -> None:
        """Store a judge result in the cache.

        Args:
            scenario_id: The scenario identifier.
            agent_config: The agent configuration.
            judge_model: The judge model name.
            artifact_hash: Hash of the run artifact content.
            result: The judge evaluation result to cache.
        """
        key = self._key(scenario_id, agent_config, judge_model, artifact_hash)
        path = self._cache_dir / f"{key}.json"
        data = {"_cached_at": time.time(), "result": result}
        path.write_text(json.dumps(data, indent=2))

    def clear(self) -> int:
        """Remove all cached judge results.

        Returns:
            The number of cache files deleted.
        """
        count = 0
        if self._cache_dir.exists():
            for f in self._cache_dir.iterdir():
                if f.suffix == ".json":
                    f.unlink()
                    count += 1
        return count

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            A dict with ``files`` count and ``size_bytes`` total.
        """
        if not self._cache_dir.exists():
            return {"files": 0, "size_bytes": 0}
        files = list(self._cache_dir.glob("*.json"))
        return {
            "files": len(files),
            "size_bytes": sum(f.stat().st_size for f in files),
        }
