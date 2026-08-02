"""Mock subprocess agent: reads JSON on stdin, echoes an envelope.

Modes are driven by ``context["mode"]`` (set via the scenario's context in
tests):

- default: echo a ``evalforge.run_envelope.v1`` envelope back.
- ``raw``: print plain text (exercises the raw-text fallback path).
- ``log_and_json``: print a log line to stderr *and* a JSON envelope to
  stdout, proving stderr is ignored and stdout is what gets parsed.
- ``fail``: write to stderr and exit non-zero (exercises the error path).
- ``slow``: sleep 30s then answer (exercises the timeout path).
"""

import json
import sys


def main() -> None:
    payload = json.loads(sys.stdin.read())
    mode = payload.get("context", {}).get("mode")
    if mode == "raw":
        print("raw text answer")
        return
    if mode == "log_and_json":
        print("some log line to stderr", file=sys.stderr)
        print(
            json.dumps(
                {
                    "schema_version": "evalforge.run_envelope.v1",
                    "status": "completed",
                    "output": {"final": "from envelope"},
                }
            )
        )
        return
    if mode == "fail":
        print("boom", file=sys.stderr)
        sys.exit(3)
    if mode == "slow":
        import time

        time.sleep(30)
        print("too late")
        return
    print(
        json.dumps(
            {
                "schema_version": "evalforge.run_envelope.v1",
                "status": "completed",
                "output": {"final": f"echo: {payload.get('input')}", "structured": None},
                "trajectory": {"steps": [{"type": "response", "content": "ok", "duration_ms": 1}]},
                "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
                "error": None,
            }
        )
    )


if __name__ == "__main__":
    main()
