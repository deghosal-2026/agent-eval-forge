"""Provenance module — tracks metadata about evaluation run origins.

Records pack hashes, agent sources, git SHAs, Python/platform details, and
dependency versions so every artifact carries auditable provenance.
"""

from evalforge.provenance.tracker import ProvenanceInfo, ProvenanceTracker

__all__ = [
    "ProvenanceInfo",
    "ProvenanceTracker",
]
