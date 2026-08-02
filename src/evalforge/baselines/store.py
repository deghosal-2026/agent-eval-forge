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
from typing import Any

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
        """Build the filesystem path for a baseline by name.

        Args:
            name: The baseline name (e.g. ``"v1.0.0"``).

        Returns:
            A Path object pointing to ``{base_dir}/{name}.json``.
        """
        return self._base / f"{name}.json"

    def save(self, baseline: Baseline) -> None:
        """Persist a baseline to disk as a JSON file.

        Creates the base directory (and parents) if they don't exist.
        Overwrites any existing file with the same name.

        Args:
            baseline: The Baseline to persist.
        """
        self._base.mkdir(parents=True, exist_ok=True)
        data = baseline.to_dict()
        data["trust"] = baseline.trust
        self._path(baseline.name).write_text(
            json.dumps(data, indent=2)
        )

    def load(self, name: str) -> Baseline:
        """Load a baseline from disk by name.

        Args:
            name: The baseline name to load.

        Returns:
            The deserialized Baseline.

        Raises:
            FileNotFoundError: If no baseline with the given name exists.
        """
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"Baseline not found: {name}")
        return Baseline.from_dict(json.loads(path.read_text()))

    def list(self) -> list[str]:
        """Return sorted list of all baseline names in the store.

        Returns an empty list if the store directory doesn't exist yet.

        Returns:
            Sorted list of baseline names (without .json extension).
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

        Args:
            name: The baseline name to validate.
            pack_version: The expected pack version string.

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

    def describe(self, name: str) -> dict[str, Any]:
        """Return a rich description dict for a baseline.

        Provides all metadata needed for display: name, pack, version,
        scenario count, average score, tags, notes, creation date, trust
        level, and git SHA.

        Args:
            name: The baseline name to describe.

        Returns:
            A dict with descriptive metadata fields.
        """
        bl = self.load(name)
        avg_score = None
        if bl.score_snapshot:
            scenario_scores = bl.score_snapshot.get("scenario_scores", {})
            scores = list(scenario_scores.values())
            avg_score = sum(scores) / len(scores) if scores else None
        return {
            "name": bl.name,
            "pack": bl.pack,
            "pack_version": bl.pack_version,
            "scenarios": len(bl.runs),
            "avg_score": avg_score,
            "tags": bl.tags,
            "notes": bl.notes,
            "trust": bl.trust,
            "git_sha": bl.git_sha,
            "created": bl.created,
        }

    def tag(self, name: str, tags: list[str]) -> Baseline:  # type: ignore[valid-type]
        """Replace the tags on a baseline and persist to disk.

        Args:
            name: The baseline name to tag.
            tags: New list of tags (replaces existing).

        Returns:
            The updated Baseline (already persisted).
        """
        bl = self.load(name)
        bl.tags = list(tags)
        self.save(bl)
        return bl

    def annotate(self, name: str, notes: str) -> Baseline:
        """Set the notes field on a baseline and persist to disk.

        Args:
            name: The baseline name to annotate.
            notes: New notes text (replaces existing).

        Returns:
            The updated Baseline (already persisted).
        """
        bl = self.load(name)
        bl.notes = notes
        self.save(bl)
        return bl

    def delete(self, name: str) -> None:
        """Delete a baseline from disk.

        Args:
            name: The baseline name to delete.

        Raises:
            FileNotFoundError: If no baseline with the given name exists.
        """
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"Baseline not found: {name}")
        path.unlink()
