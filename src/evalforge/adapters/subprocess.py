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
import shlex
import subprocess
from typing import Any

from evalforge.adapters.base import Adapter
from evalforge.models.errors import AdapterError, AgentTimeoutError


class SubprocessAdapter(Adapter):
    """Invoke an agent as a subprocess; stdin gets the invocation payload JSON."""

    name = "subprocess"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str:
        command = config.get("command")
        if not command:
            raise AdapterError("subprocess adapter requires `command` in config")
        timeout = float(config.get("timeout_seconds", 120))
        args = shlex.split(command)
        try:
            # The command comes from operator-supplied agent config (trusted),
            # not from agent/scenario data; run without a shell as a list.
            proc = subprocess.run(  # noqa: S603 - trusted config, shell=False
                args,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
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
