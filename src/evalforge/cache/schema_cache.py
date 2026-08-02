"""Thread-safe in-memory cache for pack schema validation results.

Prevents redundant schema validation of already-validated packs within
the same process lifetime.
"""

import threading


class SchemaCache:
    """Thread-safe cache tracking which pack hashes have been schema-validated.

    Uses a :class:`threading.Lock` to protect the internal set during
    concurrent access from multiple evaluation threads.
    """

    def __init__(self) -> None:
        """Initialize an empty schema validation cache."""
        self._validated: set[str] = set()
        self._lock = threading.Lock()

    def is_validated(self, pack_hash: str) -> bool:
        """Check if a pack hash has already been validated.

        Args:
            pack_hash: The pack content hash to check.

        Returns:
            True if the pack has been previously validated.
        """
        with self._lock:
            return pack_hash in self._validated

    def mark_validated(self, pack_hash: str) -> None:
        """Mark a pack hash as validated.

        Args:
            pack_hash: The pack content hash to mark.
        """
        with self._lock:
            self._validated.add(pack_hash)

    def clear(self) -> None:
        """Remove all cached validation results."""
        with self._lock:
            self._validated.clear()
