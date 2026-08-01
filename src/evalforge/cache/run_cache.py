from __future__ import annotations

from typing import Any


class RunCache:
    def __init__(self) -> None:
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def get(self, pack_hash: str) -> list[dict[str, Any]] | None:
        return self._cache.get(pack_hash)

    def set(self, pack_hash: str, artifacts: list[dict[str, Any]]) -> None:
        self._cache[pack_hash] = artifacts

    def clear(self) -> None:
        self._cache.clear()
