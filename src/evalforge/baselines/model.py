"""Baseline model — an explicit golden snapshot of accepted agent runs.

A Baseline captures the full set of RunArtifacts that were accepted at a
point in time, along with metadata about the pack, agent, and git state.
Baselines are version-checked against the scenario pack to prevent silent
comparison of incompatible versions.

Typical lifecycle:
    1. Run a scenario pack against an agent, score it -> list[RunArtifact].
    2. Save the artifacts as a Baseline via BaselineStore.save().
    3. On subsequent runs, compare candidate artifacts against this baseline.
    4. BaselineStore.validate() warns if pack versions diverge.
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
        score_snapshot: Frozen metric results from scoring, used in snapshot
            comparison mode to avoid rescoring.
        agent: Metadata about the agent that produced these runs
            (framework, version, model, etc).
        trust: Trust level at baseline creation time.
        git_sha: Git commit SHA of the codebase when this baseline was
            created. Enables traceability back to exact source.
        created: ISO-8601 timestamp of baseline creation.
        tags: Arbitrary tags for grouping/filtering baselines.
        notes: Free-text notes describing what this baseline represents.
    """

    name: str
    pack: str
    pack_version: str
    runs: list[RunArtifact]
    score_snapshot: dict[str, Any] | None = None
    agent: dict[str, Any] = field(default_factory=dict)
    trust: str = "local"
    git_sha: str | None = None
    created: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        Uses RunArtifact.model_dump(mode="json") to ensure all nested
        pydantic models are converted to plain dicts/lists/primitives.

        Returns:
            A JSON-serializable dict representation of the baseline.
        """
        return {
            "name": self.name,
            "pack": self.pack,
            "pack_version": self.pack_version,
            "score_snapshot": self.score_snapshot,
            "agent": self.agent,
            "trust": self.trust,
            "git_sha": self.git_sha,
            "created": self.created,
            "tags": self.tags,
            "notes": self.notes,
            "runs": [r.model_dump(mode="json") for r in self.runs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Baseline:
        """Deserialize from a dictionary produced by to_dict().

        Reconstructs RunArtifact pydantic models from their serialized form.
        Uses .get() for optional fields to maintain forward compatibility
        with baselines saved by older versions.

        Args:
            data: A dict produced by :meth:`to_dict`.

        Returns:
            A reconstructed Baseline instance.
        """
        runs = [RunArtifact(**r) for r in data["runs"]]
        return cls(
            name=data["name"],
            pack=data["pack"],
            pack_version=data["pack_version"],
            runs=runs,
            score_snapshot=data.get("score_snapshot"),
            agent=data.get("agent", {}),
            trust=data.get("trust", "local"),
            git_sha=data.get("git_sha"),
            created=data.get("created", ""),
            tags=data.get("tags", []),
            notes=data.get("notes", ""),
        )
