"""Project configuration loaded from evalforge.toml.

Config is read from the current working directory by default, or from a path
specified via EVALFORGE_CONFIG env var. Falls back to sensible defaults when
no config file is present.

Usage:
    from evalforge.config import load_config
    cfg = load_config()
    print(cfg.judge_provider, cfg.judge_model)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


@dataclass
class EvalForgeConfig:
    """Configuration loaded from evalforge.toml."""

    # Judge defaults
    judge_provider: str = "openai"
    judge_model: str = "gpt-4o-mini"

    # Output
    output_dir: str = ".evalforge"
    log_level: str = "info"

    # Scoring
    strict_mode: bool = False
    compare_mode: str = "snapshot"  # snapshot | rescore

    # Raw TOML data (for sub-command use)
    raw: dict[str, Any] = field(default_factory=dict)


def _find_config_file(path: str | Path | None = None) -> Path | None:
    if path:
        p = Path(path)
        if p.is_file():
            return p
        if p.is_dir():
            p = p / "evalforge.toml"
        return p if p.is_file() else None

    # Check EVALFORGE_CONFIG env var
    env_path = os.environ.get("EVALFORGE_CONFIG")
    if env_path:
        p = Path(env_path)
        return p if p.is_file() else None

    # Check cwd
    cwd = Path.cwd() / "evalforge.toml"
    return cwd if cwd.is_file() else None


def load_config(path: str | Path | None = None) -> EvalForgeConfig:
    """Load configuration from evalforge.toml.

    Returns a default config if no file is found.
    """
    config_file = _find_config_file(path)
    if config_file is None or tomllib is None:
        return EvalForgeConfig()

    try:
        data = tomllib.loads(config_file.read_text())
    except Exception:
        return EvalForgeConfig()

    raw = dict(data)

    judge_cfg = data.get("judge", {})
    output_cfg = data.get("output", {})
    scoring_cfg = data.get("scoring", {})

    return EvalForgeConfig(
        judge_provider=judge_cfg.get("provider", "openai"),
        judge_model=judge_cfg.get("model", "gpt-4o-mini"),
        output_dir=output_cfg.get("dir", ".evalforge"),
        log_level=output_cfg.get("log_level", "info"),
        strict_mode=scoring_cfg.get("strict", False),
        compare_mode=scoring_cfg.get("compare_mode", "snapshot"),
        raw=raw,
    )
