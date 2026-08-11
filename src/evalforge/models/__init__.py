"""Data models for scenarios, run artifacts, baselines, and comparisons.

These are the canonical, versioned data shapes that flow through the whole
harness (spec §"Run Artifact", §"Baseline Model", §"Comparison Model"). They
are plain serializable objects (pydantic in M1) so artifacts can be written
to `.evalforge/runs/*.json` and re-loaded identically across processes and CI
runs — determinism of stored results is a core product guarantee.

Each model must evolve under the schema evolution rules in spec §"Schema
Evolution Rules"; do not break deserialization of existing artifacts.
"""

from evalforge.models.artifact import (
    Cost,
    RunArtifact,
    RunOutput,
    RunTimestamps,
    TrajectoryStep,
)
from evalforge.models.errors import (
    AdapterError,
    AgentTimeoutError,
    EvalForgeError,
    PackParseError,
)
from evalforge.models.manifest import RunManifest, build_manifest, collect_host_info
from evalforge.models.pack import (
    Budget,
    Expected,
    Metric,
    PackMetadata,
    Scenario,
    ScenarioPack,
    Tool,
)
from evalforge.models.trace import ExecutionTrace, compute_trace_diff

__all__ = [
    "AdapterError",
    "AgentTimeoutError",
    "Budget",
    "Cost",
    "EvalForgeError",
    "ExecutionTrace",
    "Expected",
    "Metric",
    "PackMetadata",
    "PackParseError",
    "RunArtifact",
    "RunManifest",
    "RunOutput",
    "RunTimestamps",
    "Scenario",
    "ScenarioPack",
    "Tool",
    "TrajectoryStep",
    "build_manifest",
    "collect_host_info",
    "compute_trace_diff",
]
