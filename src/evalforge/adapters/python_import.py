"""Python-import adapter: call a Python function as the agent.

The callable runs in a separate process (via multiprocessing) so a hard
timeout and state isolation are guaranteed, matching the spec's worker
isolation model. The agent's contract is ``run(payload) -> dict | str`` where
``payload`` is the invocation payload dict; returning a dict is treated as a
run envelope, returning a string is treated as a plain-text final answer.

The result is shipped back over a :class:`multiprocessing.Queue` so arbitrary
agent exceptions can be captured and normalized instead of crashing the
runner.

When ``sandbox`` is enabled in config, the agent is routed through a
sandboxed subprocess instead of multiprocessing for stronger isolation.

Note: In parallel execution (workers > 1), this adapter uses
multiprocessing.Process which uses "spawn" on macOS. The combined
use of ThreadPoolExecutor + multiprocessing.Process can cause
import path issues. Prefer the subprocess adapter for parallel runs
on macOS, or set workers=1 for python_import.
"""

from __future__ import annotations

import multiprocessing
from typing import Any

from evalforge.adapters.base import Adapter, _inject_fixtures, parse_agent_stdout
from evalforge.models.errors import AdapterError, AgentTimeoutError


def _agent_worker(module: str, function: str, payload: dict[str, Any], queue: Any) -> None:
    """Run in a child process: import module, call function, send result."""
    import importlib

    try:
        mod = importlib.import_module(module)
        fn = getattr(mod, function)
        result = fn(payload)
        queue.put(("ok", result))
    except BaseException as exc:  # must propagate any failure
        queue.put(("error", f"{type(exc).__name__}: {exc}"))


class PythonImportAdapter(Adapter):
    """Invoke a Python function as the agent."""

    name = "python"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str | dict[str, Any]:
        module = config.get("module")
        if not module:
            raise AdapterError("python adapter requires `module` in config")
        function = config.get("function", "run")

        _inject_fixtures(payload, config)

        if config.get("sandbox"):
            from evalforge.adapters.subprocess_runner import run_agent_in_subprocess

            # Build an inline script that mirrors the contract of _agent_worker
            # but runs in a full subprocess rather than a multiprocessing.Process.
            # This gives us the sandbox's env stripping and timeout multiplier.
            agent_cmd = ["python", "-c", f"""
import importlib, sys, json
mod = importlib.import_module('{module}')
fn = getattr(mod, '{function}')
payload = json.loads(sys.stdin.read())
result = fn(payload)
if isinstance(result, dict):
    print(json.dumps(result))
else:
    print(result)
"""]
            # Enforce sandbox=True in the config passed to subprocess_runner
            # so SandboxConfig.enabled is set even if the top-level config
            # is ambiguous (e.g. no --sandbox CLI flag but the adapter was
            # invoked in a sandboxed context by the runner).
            config_with_sandbox = {**config, "sandbox": True}
            stdout = run_agent_in_subprocess(payload, agent_cmd, config_with_sandbox)
            return parse_agent_stdout(stdout, strict=bool(config.get("strict_output", False)))

        timeout = float(config.get("timeout_seconds", 120))
        try:
            queue: multiprocessing.Queue[tuple[str, object]] = multiprocessing.Queue()
            proc = multiprocessing.Process(
                target=_agent_worker,
                args=(module, function, payload, queue),
                daemon=True,
            )
            proc.start()
            proc.join(timeout)
            if proc.is_alive():
                proc.terminate()
                proc.join()
                raise AgentTimeoutError(f"agent exceeded {timeout}s timeout")
            if proc.exitcode != 0:
                raise AdapterError(f"agent process exited with code {proc.exitcode}")
        except multiprocessing.ProcessError as exc:
            raise AdapterError(f"agent process failed: {exc}") from exc

        try:
            status, value = queue.get(timeout=timeout)
        except Exception as exc:
            raise AdapterError(f"agent produced no result: {exc}") from exc
        if status == "error":
            raise AdapterError(str(value))
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return value
        raise AdapterError(f"agent function returned unexpected type: {type(value).__name__}")
