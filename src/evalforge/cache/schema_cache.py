import threading


class SchemaCache:
    def __init__(self) -> None:
        self._validated: set[str] = set()
        self._lock = threading.Lock()

    def is_validated(self, pack_hash: str) -> bool:
        with self._lock:
            return pack_hash in self._validated

    def mark_validated(self, pack_hash: str) -> None:
        with self._lock:
            self._validated.add(pack_hash)

    def clear(self) -> None:
        with self._lock:
            self._validated.clear()
