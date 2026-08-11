"""Scenario registry — discovers and indexes scenario packs on the filesystem."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class PackInfo:
    """Metadata about a discovered scenario pack.

    Attributes:
        name: Pack name (from ``pack.name`` in the file).
        version: Pack version (from ``pack.version``; defaults to ``"unknown"``).
        path: Filesystem path to the pack file.
        scenario_count: Number of scenarios in the pack.
        description: Pack description (from ``pack.description``).
    """
    name: str
    version: str
    path: Path
    scenario_count: int
    description: str = ""


class ScenarioRegistry:
    """Discovers and indexes scenario packs on the filesystem.

    Searches directories for ``.yaml``, ``.yml``, and ``.json`` files,
    parses their ``pack`` metadata section, and registers them for later
    lookup by name.
    """

    def __init__(self) -> None:
        self._packs: dict[str, PackInfo] = {}
        self._paths: list[Path] = []

    def discover(self, search_paths: list[str] | None = None) -> list[PackInfo]:
        """Discover all scenario packs in search paths.

        Searches for ``.yaml``, ``.yml``, and ``.json`` files in each
        directory and registers any valid packs found.

        Args:
            search_paths: Directories to search. Defaults to ``["scenarios"]``.

        Returns:
            List of discovered :class:`PackInfo` entries.
        """
        if search_paths is None:
            search_paths = ["scenarios"]

        discovered: list[PackInfo] = []

        for search_path in search_paths:
            root = Path(search_path)
            if not root.is_dir():
                continue
            for pattern in ("*.yaml", "*.yml", "*.json"):
                for file_path in sorted(root.rglob(pattern)):
                    info = self._read_pack_metadata(file_path)
                    if info is not None:
                        self._packs[info.name] = info
                        self._paths.append(file_path)
                        discovered.append(info)

        return discovered

    def add(self, path: str | Path) -> PackInfo | None:
        """Register a scenario pack from a specific file path.

        Args:
            path: Path to a ``.yaml``, ``.yml``, or ``.json`` pack file.

        Returns:
            :class:`PackInfo` if the pack is valid, or ``None``.
        """
        file_path = Path(path)
        info = self._read_pack_metadata(file_path)
        if info is not None:
            self._packs[info.name] = info
            self._paths.append(file_path)
        return info

    def list(self) -> list[PackInfo]:
        """List all registered scenario packs with metadata.

        Returns:
            List of :class:`PackInfo` entries sorted by name.
        """
        return sorted(self._packs.values(), key=lambda p: p.name)

    def find(self, pack_name: str) -> PackInfo | None:
        """Find a scenario pack by name.

        Args:
            pack_name: The pack name to look up.

        Returns:
            :class:`PackInfo` if found, or ``None``.
        """
        return self._packs.get(pack_name)

    # ------------------------------------------------------------------

    @staticmethod
    def _read_pack_metadata(file_path: Path) -> PackInfo | None:
        """Attempt to extract pack metadata from a file.

        Returns ``None`` for files that cannot be parsed or lack the
        required ``pack.name`` field.
        """
        try:
            raw = file_path.read_text(encoding="utf-8")
        except OSError:
            return None

        suffix = file_path.suffix.lower()
        if suffix == ".json":
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return None
        else:
            if yaml is None:
                return None
            try:
                data = yaml.safe_load(raw)
            except yaml.YAMLError:
                return None

        if not isinstance(data, dict):
            return None

        pack = data.get("pack")
        if not isinstance(pack, dict):
            return None

        name = pack.get("name")
        if not isinstance(name, str) or not name:
            return None

        version = pack.get("version", "unknown")
        if not isinstance(version, str):
            version = "unknown"

        description = pack.get("description", "")
        if not isinstance(description, str):
            description = ""

        scenarios = data.get("scenarios")
        scenario_count = len(scenarios) if isinstance(scenarios, list) else 0

        return PackInfo(
            name=name,
            version=version,
            path=file_path,
            scenario_count=scenario_count,
            description=description,
        )
