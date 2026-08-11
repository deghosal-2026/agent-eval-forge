"""Provenance tracker — captures environment and artifact metadata for auditability.

Records pack hashes, agent source hashes, git revision, Python version,
platform info, and dependency versions. Provides verification helpers to
detect drift after the fact.
"""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ProvenanceInfo:
    """Auditable provenance metadata for an evaluation run.

    Attributes:
        pack_uri: URI or file path of the scenario pack.
        pack_hash: SHA-256 hex digest of the pack file.
        pack_version: Version string from the pack metadata.
        agent_source: Agent spec string (file path or ``type:path``).
        agent_hash: SHA-256 hex digest of the agent source file.
        evalforge_version: Version of the EvalForge library.
        judge_model: Model identifier used for judging.
        git_sha: Git commit SHA at the time of the run.
        timestamp: ISO-8601 timestamp of the run.
        python_version: Python interpreter version.
        platform: OS/platform description.
        dependencies: Map of dependency name → installed version.
    """
    pack_uri: str = ""
    pack_hash: str = ""
    pack_version: str = ""
    agent_source: str = ""
    agent_hash: str = ""
    evalforge_version: str = ""
    judge_model: str = ""
    git_sha: str = ""
    timestamp: str = ""
    python_version: str = ""
    platform: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)


class ProvenanceTracker:
    """Captures environmental and artifact provenance metadata."""

    def capture(self) -> ProvenanceInfo:
        """Capture a snapshot of the current environment.

        Returns:
            A :class:`ProvenanceInfo` with timestamp, Python version,
            EvalForge version, platform, dependencies, and git SHA.
        """
        info = ProvenanceInfo()
        info.timestamp = datetime.now(UTC).isoformat()
        info.python_version = platform.python_version()
        info.evalforge_version = _get_evalforge_version()
        info.platform = platform.platform()
        info.dependencies = _get_dependencies()
        info.git_sha = _get_git_sha()
        return info

    def capture_pack(self, pack_path: str) -> ProvenanceInfo:
        """Capture environment info plus pack-specific provenance.

        Computes the pack file hash and, if the file is YAML/JSON, extracts
        the ``pack.version`` metadata field.

        Args:
            pack_path: Path to the scenario pack file.

        Returns:
            A :class:`ProvenanceInfo` with pack details.
        """
        info = self.capture()
        info.pack_uri = str(pack_path)
        info.pack_hash = self.compute_file_hash(pack_path)

        if pack_path.endswith((".yaml", ".yml", ".json")):
            try:
                import yaml
                with open(pack_path, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                pack_meta = data.get("pack", {}) if isinstance(data, dict) else {}
                info.pack_version = str(pack_meta.get("version", ""))
            except Exception:
                info.pack_version = ""

        return info

    def capture_agent(self, agent_spec: str) -> ProvenanceInfo:
        """Capture environment info plus agent-specific provenance.

        Computes the agent file hash if *agent_spec* is a local file path
        or a ``type:path`` specifier.

        Args:
            agent_spec: Agent specification string (file path or ``type:path``).

        Returns:
            A :class:`ProvenanceInfo` with agent details.
        """
        info = self.capture()
        info.agent_source = agent_spec

        if os.path.isfile(agent_spec):
            info.agent_hash = self.compute_file_hash(agent_spec)
        elif ":" in agent_spec:
            parts = agent_spec.split(":", 1)
            if os.path.isfile(parts[-1]):
                info.agent_hash = self.compute_file_hash(parts[-1])
        return info

    def to_artifact_metadata(self) -> dict[str, Any]:
        """Capture environment info and return it as a nested dict for artifact storage.

        Returns:
            Dict with a single ``provenance`` key containing all captured fields.
        """
        info = self.capture()
        return {
            "provenance": {
                "evalforge_version": info.evalforge_version,
                "timestamp": info.timestamp,
                "python_version": info.python_version,
                "platform": info.platform,
                "git_sha": info.git_sha,
                "dependencies": info.dependencies,
                "pack_uri": info.pack_uri,
                "pack_hash": info.pack_hash,
                "pack_version": info.pack_version,
                "agent_source": info.agent_source,
                "agent_hash": info.agent_hash,
                "judge_model": info.judge_model,
            }
        }

    @staticmethod
    def verify(info: ProvenanceInfo) -> list[str]:
        """Verify a :class:`ProvenanceInfo` record for internal consistency.

        Checks:
        - Timestamp is valid ISO-8601.
        - ``evalforge_version`` is present.
        - If ``pack_uri`` is set, ``pack_hash`` must also be set.
        - If ``agent_source`` is set, ``agent_hash`` must be set.
        - If ``pack_uri`` points to an existing file, its current hash
          must match the recorded ``pack_hash`` (drift detection).

        Args:
            info: The :class:`ProvenanceInfo` to verify.

        Returns:
            List of issue descriptions (empty if all checks pass).
        """
        issues: list[str] = []

        if info.timestamp:
            try:
                datetime.fromisoformat(info.timestamp)
            except ValueError:
                issues.append("timestamp is not a valid ISO-8601 string")

        if not info.evalforge_version:
            issues.append("evalforge_version is missing")

        if info.pack_uri and not info.pack_hash:
            issues.append("pack_hash is missing when pack_uri is set")

        if info.agent_source and not info.agent_hash:
            issues.append("agent_hash is missing when agent_source is set")

        if info.pack_uri and info.pack_hash:
            if os.path.isfile(info.pack_uri):
                current_hash = ProvenanceTracker.compute_file_hash(info.pack_uri)
                if current_hash != info.pack_hash:
                    issues.append(
                        f"pack_hash mismatch: recorded {info.pack_hash[:12]}..."
                        f" but current is {current_hash[:12]}..."
                    )

        return issues

    @staticmethod
    def compute_content_hash(content: str | bytes) -> str:
        """Compute the SHA-256 hex digest of a string or byte content.

        Args:
            content: The content to hash.

        Returns:
            Lowercase hex digest string.
        """
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def compute_file_hash(filepath: str) -> str:
        """Compute the SHA-256 hex digest of a file (streaming, 8K buffer).

        Args:
            filepath: Path to the file.

        Returns:
            Lowercase hex digest string.
        """
        hasher = hashlib.sha256()
        with open(filepath, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


def _get_evalforge_version() -> str:
    """Return the installed version of the ``evalforge`` package."""
    try:
        from evalforge import __version__
        return __version__
    except Exception:
        return "unknown"


def _get_dependencies() -> dict[str, str]:
    """Return a dict of all installed distribution names and versions."""
    deps: dict[str, str] = {}
    try:
        from importlib.metadata import packages_distributions, version

        pkg_map = packages_distributions()
        for _pkg_name, dist_names in pkg_map.items():
            for dist_name in dist_names:
                try:
                    deps[dist_name] = version(dist_name)
                except Exception:  # noqa: S110
                    pass
    except Exception:  # noqa: S110
        pass
    return deps


def _get_git_sha() -> str:
    """Return the current HEAD commit SHA, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:  # noqa: S110
        pass
    return ""
