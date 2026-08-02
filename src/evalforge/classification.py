"""Agent infrastructure classification tags.

Standardized tags that describe an agent's infrastructure requirements
so the runner, sandbox, and CI can make informed decisions about isolation,
resource allocation, and environment setup.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar


class InfraTags:
    """Standardized agent infrastructure classification tags."""

    NEEDS_GATEWAY = "needs_gateway"
    WRITES_ROOT = "writes_root"
    NEEDS_DB = "needs_db"
    IMPORT_SIDE_EFFECTS = "import_side_effects"
    NEEDS_GPU = "needs_gpu"
    NEEDS_API_KEY = "needs_api_key"
    NETWORK_ACCESS = "network_access"
    FILESYSTEM_WRITE = "filesystem_write"

    ALL_TAGS: ClassVar[list[str]] = [
        NEEDS_GATEWAY,
        WRITES_ROOT,
        NEEDS_DB,
        IMPORT_SIDE_EFFECTS,
        NEEDS_GPU,
        NEEDS_API_KEY,
        NETWORK_ACCESS,
        FILESYSTEM_WRITE,
    ]

    _API_KEY_PATTERNS = re.compile(
        r"(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|API_KEY|TOKEN|SECRET)", re.IGNORECASE
    )
    _NETWORK_PATTERNS = re.compile(
        r"(?:httpx|requests|aiohttp|urllib|socket|http\.client|fetch|curl)", re.IGNORECASE
    )
    _FS_WRITE_PATTERNS = re.compile(
        r"(?:open\(|Path\(|\.write_text|\.write_bytes|os\.mkdir|os\.makedirs|shutil\.|"
        r"\.save\(|with open)", re.IGNORECASE
    )
    _DB_PATTERNS = re.compile(
        r"(?:sqlite|psycopg|sqlalchemy|asyncpg|pymongo|redis|dynamodb)", re.IGNORECASE
    )
    _GPU_PATTERNS = re.compile(r"(?:torch\.cuda|gpu|cuda|metal|mps)", re.IGNORECASE)
    _SIDE_EFFECT_PATTERNS = re.compile(
        r"(?:os\.environ|sys\.path|logging\.basicConfig|atexit|signal\.signal)", re.IGNORECASE
    )


class AgentClassifier:
    """Classifies agents based on their infrastructure requirements."""

    @staticmethod
    def classify(agent_config: dict[str, Any]) -> list[str]:
        """Classify an agent config and return infra tags."""
        tags: list[str] = []
        config_str = str(agent_config)

        env_vars = agent_config.get("env", {})
        env_str = str(env_vars) if env_vars else ""
        if InfraTags._API_KEY_PATTERNS.search(env_str) or InfraTags._API_KEY_PATTERNS.search(
            config_str
        ):
            tags.append(InfraTags.NEEDS_API_KEY)

        if InfraTags._NETWORK_PATTERNS.search(config_str):
            tags.append(InfraTags.NETWORK_ACCESS)
            tags.append(InfraTags.NEEDS_GATEWAY)

        if InfraTags._FS_WRITE_PATTERNS.search(config_str):
            tags.append(InfraTags.FILESYSTEM_WRITE)
            if "root" in config_str.lower() or "/etc/" in config_str:
                tags.append(InfraTags.WRITES_ROOT)

        if InfraTags._DB_PATTERNS.search(config_str):
            tags.append(InfraTags.NEEDS_DB)

        if InfraTags._GPU_PATTERNS.search(config_str):
            tags.append(InfraTags.NEEDS_GPU)

        if InfraTags._SIDE_EFFECT_PATTERNS.search(config_str):
            tags.append(InfraTags.IMPORT_SIDE_EFFECTS)

        return list(dict.fromkeys(tags))

    @staticmethod
    def from_source(source: str) -> list[str]:
        """Inspect agent source code for infra requirements."""
        tags: list[str] = []

        if InfraTags._API_KEY_PATTERNS.search(source):
            tags.append(InfraTags.NEEDS_API_KEY)
        if InfraTags._NETWORK_PATTERNS.search(source):
            tags.append(InfraTags.NETWORK_ACCESS)
        if InfraTags._FS_WRITE_PATTERNS.search(source):
            tags.append(InfraTags.FILESYSTEM_WRITE)
        if InfraTags._DB_PATTERNS.search(source):
            tags.append(InfraTags.NEEDS_DB)
        if InfraTags._GPU_PATTERNS.search(source):
            tags.append(InfraTags.NEEDS_GPU)
        if InfraTags._SIDE_EFFECT_PATTERNS.search(source):
            tags.append(InfraTags.IMPORT_SIDE_EFFECTS)

        return list(dict.fromkeys(tags))
