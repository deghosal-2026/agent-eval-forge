"""Mock python-import agents.

Modes are driven by ``payload["context"]["mode"]`` (set via the scenario's
context in tests):

- default: return a ``evalforge.run_envelope.v1`` envelope dict.
- ``raw``: return a plain string (exercises the raw-text fallback path).
- ``error``: raise a ``RuntimeError`` (exercises the error path).
- ``slow``: sleep 30s then return (exercises the timeout path).
"""

import os
import time


def run(payload: dict) -> dict | str:
    mode = payload.get("context", {}).get("mode", "envelope")
    if mode == "raw":
        return "raw python answer"
    if mode == "error":
        raise RuntimeError("agent blew up")
    if mode == "slow":
        time.sleep(30)
        return "too slow"
    if mode == "hard_exit":
        os._exit(1)
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": f"py:{payload.get('input')}", "structured": None},
        "trajectory": {"steps": [{"type": "response", "content": "ok", "duration_ms": 1}]},
        "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
        "error": None,
    }
