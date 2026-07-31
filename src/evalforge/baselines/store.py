"""Baseline store — filesystem persistence for golden baselines.

Stores baselines as individual JSON files under a configurable base
directory (default: .evalforge/baselines/). Each baseline is written as
<name>.json containing the full Baseline.to_dict() output.

Thread safety: Not guaranteed for concurrent save/load on the same
baseline name. Intended for single-process usage (CLI commands, CI runs).

The directory structure is:
    .evalforge/baselines/
    ├── v1.0.0.json
    ├── v1.1.0.json
    └── ...  # one file per named baseline
"""

from __future__ import annotations

import json
from pathlib import Path

from evalforge.baselines.model import Baseline


class BaselineStore:
    """Filesystem-backed store for Baseline snapshots.

    Args:
        base_dir: Directory under which baseline JSON files are stored.
            Created automatically on first save if it doesn't exist.
    """

    def __init__(self, base_dir: str = ".evalforge/baselines") -> None:
        self._base = Path(base_dir)

    def _path(self, name: str) -> Path:
        """Build the filesystem path for a baseline by name."""
        return self._base / f"{name}.json"

    def save(self, baseline: Baseline) -> None:
        """Persist a baseline to disk as a JSON file.

        Creates the base directory (and parents) if they don't exist.
        Overwrites any existing file with the same name.
        """
        self._base.mkdir(parents=True, exist_ok=True)
        self._path(baseline.name).write_text(
            json.dumps(baseline.to_dict(), indent=2)
        )

    def load(self, name: str) -> Baseline:
        """Load a baseline from disk by name.

        Raises FileNotFoundError if no baseline with the given name exists.
        """
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"Baseline not found: {name}")
        return Baseline.from_dict(json.loads(path.read_text()))

    def list(self) -> list[str]:
        """Return sorted list of all baseline names in the store.

        Returns an empty list if the store directory doesn't exist yet.
        """
        if not self._base.exists():
            return []
        return sorted(
            p.stem for p in self._base.iterdir() if p.suffix == ".json"
        )

    def validate(self, name: str, pack_version: str) -> str:
        """Check that a baseline's pack version matches the expected version.

        This is a warning-only check — it returns a descriptive message on
        mismatch rather than raising. The caller decides how to handle it
        (e.g., log a warning in CI, prompt the user in CLI).

        Returns:
            Empty string if versions match.
            Human-readable warning if versions differ.
        """
        baseline = self.load(name)
        if baseline.pack_version != pack_version:
            return (
                f"version mismatch: baseline={baseline.pack_version}, "
                f"pack={pack_version}"
            )
        return ""
