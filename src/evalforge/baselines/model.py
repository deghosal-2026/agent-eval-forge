"""Baseline model — an explicit golden snapshot of accepted agent runs.

A Baseline captures the full set of RunArtifacts that were accepted at a
point in time, along with metadata about the pack, agent, and git state.
Baselines are version-checked against the scenario pack to prevent silent
comparison of incompatible versions.

Typical lifecycle:
    1. Run a scenario pack against an agent, score it → list[RunArtifact]
    2. Save the artifacts as a Baseline via BaselineStore.save()
    3. On subsequent runs, compare candidate artifacts against this baseline
    4. BaselineStore.validate() warns if pack versions diverge
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from evalforge.models.artifact import RunArtifact


@dataclass
class Baseline:
    """A golden snapshot of accepted run artifacts for a scenario pack.

    Fields:
        name: Human-readable baseline identifier (e.g. "v1.0.0").
        pack: Name of the scenario pack this baseline covers.
        pack_version: Semver of the pack at baseline creation time. Used by
            BaselineStore.validate() to detect version drift.
        runs: All RunArtifacts that represent the accepted state. One per
            scenario in the pack.
        agent: Metadata about the agent that produced these runs
            (framework, version, model, etc).
        git_sha: Git commit SHA of the codebase when this baseline was
            created. Enables traceability back to exact source.
        created: ISO-8601 timestamp of baseline creation.
    """

    name: str
    pack: str
    pack_version: str
    runs: list[RunArtifact]
    agent: dict[str, Any] = field(default_factory=dict)
    git_sha: str | None = None
    created: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        Uses RunArtifact.model_dump(mode="json") to ensure all nested
        pydantic models are converted to plain dicts/lists/primitives.
        """
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
        """Deserialize from a dictionary produced by to_dict().

        Reconstructs RunArtifact pydantic models from their serialized form.
        Uses .get() for optional fields to maintain forward compatibility
        with baselines saved by older versions.
        """
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
