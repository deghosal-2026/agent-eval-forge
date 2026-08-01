"""Subprocess adapter: invoke an executable agent with JSON on stdin.

The agent contract (spec §"Agent is an executable"): EvalForge launches the
agent command, passes the invocation payload as JSON on stdin, captures
stdout, and requires a clean exit code. Agent stderr is ignored for output
parsing (it is surfaced in error messages when the process fails).

Security: commands run without a shell (``shell=False``) so config-supplied
command strings cannot be chained with shell metacharacters.
"""

from __future__ import annotations

import shlex
from typing import Any

from evalforge.adapters.base import Adapter, _inject_fixtures
from evalforge.models.errors import AdapterError
from evalforge.adapters.subprocess_runner import run_agent_in_subprocess


class SubprocessAdapter(Adapter):
    """Invoke an agent as a subprocess; stdin gets the invocation payload JSON."""

    name = "subprocess"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str:
        command = config.get("command")
        if not command:
            raise AdapterError("subprocess adapter requires `command` in config")
        args = shlex.split(command)
        _inject_fixtures(payload, config)
        return run_agent_in_subprocess(payload, args, config)
