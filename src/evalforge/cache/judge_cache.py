from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, cast


class JudgeCache:
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
            if not isinstance(data, dict):
                return None
            age = time.time() - data.get("_cached_at", 0)
            if age > self._ttl_seconds:
                path.unlink(missing_ok=True)
                return None
            result = data.get("result")
            if isinstance(result, dict):
                return cast(dict[str, Any], result)
            return None
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
