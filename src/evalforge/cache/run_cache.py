"""In-memory cache for run artifacts.

Stores evaluation run results keyed by pack hash to avoid re-running
scenarios with identical pack content within the same process.
"""

from __future__ import annotations

from typing import Any


class RunCache:
    """In-memory cache for run artifacts keyed by pack hash.

    Used during evaluation to skip re-running scenarios whose pack content
    has not changed since the last evaluation within the same process lifetime.
    """

    def __init__(self) -> None:
        """Initialize an empty run cache."""
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def get(self, pack_hash: str) -> list[dict[str, Any]] | None:
        """Retrieve cached artifacts for a pack hash.

        Args:
            pack_hash: The pack content hash.

        Returns:
            The cached artifact list, or ``None`` if not cached.
        """
        return self._cache.get(pack_hash)

    def set(self, pack_hash: str, artifacts: list[dict[str, Any]]) -> None:
        """Cache artifacts for a pack hash.

        Args:
            pack_hash: The pack content hash.
            artifacts: The list of run artifacts to cache.
        """
        self._cache[pack_hash] = artifacts

    def clear(self) -> None:
        """Remove all cached run artifacts."""
        self._cache.clear()
