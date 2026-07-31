"""Baseline store — filesystem persistence for golden baselines."""

from __future__ import annotations

import json
from pathlib import Path

from evalforge.baselines.model import Baseline


class BaselineStore:
    def __init__(self, base_dir: str = ".evalforge/baselines") -> None:
        self._base = Path(base_dir)

    def _path(self, name: str) -> Path:
        return self._base / f"{name}.json"

    def save(self, baseline: Baseline) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        self._path(baseline.name).write_text(
            json.dumps(baseline.to_dict(), indent=2)
        )

    def load(self, name: str) -> Baseline:
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"Baseline not found: {name}")
        return Baseline.from_dict(json.loads(path.read_text()))

    def list(self) -> list[str]:
        if not self._base.exists():
            return []
        return sorted(
            p.stem for p in self._base.iterdir() if p.suffix == ".json"
        )

    def validate(self, name: str, pack_version: str) -> str:
        baseline = self.load(name)
        if baseline.pack_version != pack_version:
            return (
                f"version mismatch: baseline={baseline.pack_version}, "
                f"pack={pack_version}"
            )
        return ""
