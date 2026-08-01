"""Subprocess adapter: invoke an executable agent with JSON on stdin.

The agent contract (spec §"Agent is an executable"): EvalForge launches the
agent command, passes the invocation payload as JSON on stdin, captures
stdout, and requires a clean exit code. Agent stderr is ignored for output
parsing (it is surfaced in error messages when the process fails).

Security: commands run without a shell (``shell=False``) so config-supplied
command strings cannot be chained with shell metacharacters.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any

from evalforge.adapters.base import Adapter, _inject_fixtures
from evalforge.models.errors import AdapterError, AgentTimeoutError
from evalforge.security.sandbox import SandboxConfig, sandboxed_run


class SubprocessAdapter(Adapter):
    """Invoke an agent as a subprocess; stdin gets the invocation payload JSON."""

    name = "subprocess"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str:
        command = config.get("command")
        if not command:
            raise AdapterError("subprocess adapter requires `command` in config")
        timeout = float(config.get("timeout_seconds", 120))
        args = shlex.split(command)

        _inject_fixtures(payload, config)

        sandbox = SandboxConfig(
            enabled=bool(config.get("sandbox", False)),
        )

        extra_env: dict[str, str] | None = None
        if config.get("fixtures"):
            extra_env = {
                "EVALFORGE_FIXTURES": "1",
                "EVALFORGE_FIXTURES_DIR": config.get("fixtures_dir", "scenarios/fixtures"),
            }

        try:
            result = sandboxed_run(
                args=args,
                config=sandbox,
                env=extra_env,
                timeout=timeout,
                input=json.dumps(payload),
            )
            proc = result
        except subprocess.TimeoutExpired as exc:
            raise AgentTimeoutError(f"agent exceeded {timeout}s timeout") from exc
        except OSError as exc:
            raise AdapterError(f"failed to launch agent: {exc}") from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise AdapterError(
                f"agent exited with code {proc.returncode}: {stderr or '(no stderr)'}"
            )
        return proc.stdout or ""
