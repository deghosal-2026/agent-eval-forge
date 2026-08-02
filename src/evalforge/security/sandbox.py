"""Sandbox for running untrusted scenario packs.

When ``--sandbox`` is enabled, the subprocess adapter:
- Strips all env vars except a minimal allowlist
- Sets ``EVALFORGE_SANDBOX=1`` in the child process
- Adds a 2x timeout multiplier to prevent DoS
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
import json
import time
import uuid

# Minimal env vars allowed in sandbox mode
SANDBOX_ALLOWLIST = {
    "PATH", "HOME", "TMPDIR", "USER",
    "EVALFORGE_SANDBOX", "EVALFORGE_FIXTURES_DIR",
}


@dataclass
class SandboxConfig:
    """Configuration for sandboxed agent execution."""
    enabled: bool = False
    allowlist: set[str] = field(default_factory=lambda: SANDBOX_ALLOWLIST)
    timeout_multiplier: float = 2.0


def sandboxed_run(
    args: list[str],
    config: SandboxConfig,
    env: dict[str, str] | None = None,
    timeout: float = 120.0,
    input: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with sandbox restrictions.

    S603 notes: ``subprocess.run`` is called with user-supplied args (the agent
    command), but this is the security boundary — all callers go through trust
    policy enforcement before reaching this function. The env stripping here
    is the primary sandbox mechanism.
    """
    if not config.enabled:
        # Non-sandboxed path: pass through all env vars for compatibility.
        # The trust policy already verified this is an allowed combination.
        return subprocess.run(  # noqa: S603
            args,
            input=input,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
        )

    sandbox_env: dict[str, str] = {"EVALFORGE_SANDBOX": "1"}
    for key in config.allowlist:
        if key in os.environ:
            sandbox_env[key] = os.environ[key]
    if env:
        for key in config.allowlist.intersection(env):
            sandbox_env[key] = env[key]

    return subprocess.run(  # noqa: S603
        args,
        input=input,
        capture_output=True,
        text=True,
        timeout=timeout * config.timeout_multiplier,
        env=sandbox_env,
    )


@dataclass
class DockerConfig:
    """Configuration for Docker-based agent execution."""
    image: str = "evalforge-agent-runner"
    network_disabled: bool = True
    read_only_root: bool = True
    memory_limit: str = "512m"
    cpu_limit: float = 1.0


def run_in_container(
    agent_cmd: list[str],
    payload_str: str,
    config: DockerConfig,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Run an agent inside a Docker container with isolation."""
    docker_args = ["docker", "run", "--rm"]
    if config.network_disabled:
        docker_args.extend(["--network", "none"])
    if config.read_only_root:
        docker_args.extend(["--read-only"])
    if config.memory_limit:
        docker_args.extend(["--memory", config.memory_limit])
    if config.cpu_limit:
        docker_args.extend(["--cpus", str(config.cpu_limit)])
    # S108: tmpfs path is hardcoded and non-configurable — this is intentional
    # for the Docker sandbox to prevent accidental FS writes. The tmpfs is
    # ephemeral and limited to 64MB, so no realistic risk of filling /tmp.
    docker_args.extend(["--tmpfs", "/tmp:noexec,nosuid,size=64m"])  # noqa: S108
    docker_args.append(config.image)
    docker_args.extend(agent_cmd)

    started_ts = time.time()
    result = subprocess.run(  # noqa: S603
        docker_args,
        input=payload_str,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    finished_ts = time.time()

    # Optional logging of container interactions for test artifacts.
    log_dir = os.environ.get("EVALFORGE_DOCKER_LOG_DIR")
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
            entry_dir = os.path.join(
                log_dir,
                f"run-{int(started_ts*1000)}-{os.getpid()}-{uuid.uuid4().hex[:8]}",
            )
            os.makedirs(entry_dir, exist_ok=True)
            with open(os.path.join(entry_dir, "stdout.txt"), "w", encoding="utf-8") as f_out:
                f_out.write(result.stdout or "")
            with open(os.path.join(entry_dir, "stderr.txt"), "w", encoding="utf-8") as f_err:
                f_err.write(result.stderr or "")
            meta = {
                "agent_cmd": agent_cmd,
                "payload_len": len(payload_str or ""),
                "docker_args": docker_args,
                "returncode": result.returncode,
                "started_ts": started_ts,
                "finished_ts": finished_ts,
                "duration_sec": finished_ts - started_ts,
                "config": {
                    "image": config.image,
                    "network_disabled": config.network_disabled,
                    "read_only_root": config.read_only_root,
                    "memory_limit": config.memory_limit,
                    "cpu_limit": config.cpu_limit,
                },
            }
            with open(os.path.join(entry_dir, "meta.json"), "w", encoding="utf-8") as f_meta:
                json.dump(meta, f_meta, indent=2)
        except Exception:
            # Logging should never break execution
            pass

    return result
