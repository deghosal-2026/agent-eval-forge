class SchemaCache:
    def __init__(self) -> None:
        self._validated: set[str] = set()

    def is_validated(self, pack_hash: str) -> bool:
        return pack_hash in self._validated

    def mark_validated(self, pack_hash: str) -> None:
        self._validated.add(pack_hash)

    def clear(self) -> None:
        self._validated.clear()