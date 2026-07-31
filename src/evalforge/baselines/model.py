"""Baseline model — an explicit golden snapshot of accepted agent runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from evalforge.models.artifact import RunArtifact


@dataclass
class Baseline:
    name: str
    pack: str
    pack_version: str
    runs: list[RunArtifact]
    agent: dict[str, Any] = field(default_factory=dict)
    git_sha: str | None = None
    created: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pack": self.pack,
            "pack_version": self.pack_version,
            "agent": self.agent,
            "git_sha": self.git_sha,
            "created": self.created,
            "runs": [r.model_dump(mode="json") for r in self.runs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Baseline:
        runs = [RunArtifact(**r) for r in data["runs"]]
        return cls(
            name=data["name"],
            pack=data["pack"],
            pack_version=data["pack_version"],
            runs=runs,
            agent=data.get("agent", {}),
            git_sha=data.get("git_sha"),
            created=data.get("created", ""),
        )
