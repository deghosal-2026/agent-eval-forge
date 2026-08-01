"""Common subprocess runner for sandboxed agent execution.
Used by subprocess adapter and (when sandboxed) by python_import adapter.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from evalforge.models.errors import AdapterError, AgentTimeoutError
from evalforge.security.sandbox import DockerConfig, SandboxConfig, run_in_container, sandboxed_run


def run_agent_in_subprocess(
    payload: dict[str, Any],
    agent_cmd: list[str],
    config: dict[str, Any],
) -> str:
    """Run an agent command with JSON payload on stdin, return stdout."""
    timeout = float(config.get("timeout_seconds", 120))
    sandbox = SandboxConfig(enabled=bool(config.get("sandbox", False)))
    extra_env: dict[str, str] = {}

    if config.get("container_runtime") == "docker":
        dc = DockerConfig()
        result = run_in_container(agent_cmd, json.dumps(payload), dc, timeout)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise AdapterError(f"container exited with code {result.returncode}: {stderr or '(no stderr)'}")
        return result.stdout or ""

    if config.get("fixtures"):
        extra_env["EVALFORGE_FIXTURES"] = "1"
        extra_env["EVALFORGE_FIXTURES_DIR"] = config.get("fixtures_dir", "scenarios/fixtures")
    try:
        result = sandboxed_run(
            args=agent_cmd,
            config=sandbox,
            timeout=timeout,
            input=json.dumps(payload),
            env=extra_env,
        )
    except subprocess.TimeoutExpired:
        raise AgentTimeoutError(f"agent exceeded {timeout}s timeout")
    except OSError as exc:
        raise AdapterError(f"failed to launch agent: {exc}")
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise AdapterError(
            f"agent exited with code {result.returncode}: {stderr or '(no stderr)'}"
        )
    return result.stdout or ""
