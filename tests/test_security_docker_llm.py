"""Docker + LLM smoke test: call omlx from inside the container.

Calls the local omlx server (http://127.0.0.1:8000/v1 on the host) from inside
the evalforge Docker image. From the container's perspective, the host is
reached via host.docker.internal. No guards — if Docker isn't running or omlx
isn't reachable, the test fails.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess

import pytest

from evalforge.security.sandbox import DockerConfig, run_in_container

pytestmark = [pytest.mark.docker]

DOCKER_IMAGE = os.environ.get("EVALFORGE_DOCKER_IMAGE", "evalforge-agent-runner")

# omlx runs on the host at 127.0.0.1:8000/v1. From inside Docker on macOS,
# host services are reachable via host.docker.internal. On Linux,
# add_host_gateway=True maps host.docker.internal to the host gateway.
OMLX_URL = "http://host.docker.internal:8000/v1/chat/completions"


def _omlx_available_host() -> bool:
    """Detect OMLX from either host or container contexts.

    - On host: 127.0.0.1:8000
    - In container: host.docker.internal:8000 (Docker Desktop),
      else still try 127.0.0.1 for compatibility.
    """
    def _try(host: str) -> bool:
        try:
            for res in socket.getaddrinfo(host, 8000, socket.AF_UNSPEC, socket.SOCK_STREAM):
                af, socktype, proto, _canonname, sa = res
                s = socket.socket(af, socktype, proto)
                s.settimeout(1.0)
                try:
                    s.connect(sa)
                    s.close()
                    return True
                except OSError:
                    s.close()
                    continue
        except OSError:
            return False
        return False

    return _try("127.0.0.1") or _try("host.docker.internal")


@pytest.fixture(autouse=True)
def require_docker() -> None:
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=True)  # noqa: S603, S607
    except Exception:
        pytest.fail("Docker daemon is not running — start Docker Desktop and retry")


@pytest.fixture(autouse=True)
def ensure_image() -> None:
    try:
        subprocess.run(  # noqa: S603
            ["docker", "image", "inspect", DOCKER_IMAGE],  # noqa: S607
            capture_output=True, timeout=10, check=True,
        )
    except Exception:
        pytest.fail(
            f"Required Docker image '{DOCKER_IMAGE}' not found. "
            "Build or load it explicitly before running docker tests."
        )


@pytest.fixture(autouse=True)
def require_omlx() -> None:
    # Explicit fail (not skip) when OMLX is not reachable on the host
    if not _omlx_available_host():
        pytest.fail("OMLX not detected at http://127.0.0.1:8000 — start OMLX and retry")


def test_omlx_chat_completion_in_container() -> None:
    """Call omlx from inside the Docker container and assert non-blank output."""
    # Use a model commonly available in OMLX by default
    payload_body = (
        '{"model":"Qwen3.5-9B-MLX-4bit","messages":'
        '[{"role":"user","content":"Say hello in one word."}],"max_tokens":10}'
    )

    # Inline Python that POSTs to omlx and prints the response
    py = (
        "import httpx; "
        f"r=httpx.post('{OMLX_URL}', content={payload_body!r}, "
        "headers={'Content-Type':'application/json'}, timeout=30.0); "
        "print(r.status_code); print(r.text)"
    )

    cfg = DockerConfig(
        image=DOCKER_IMAGE,
        network_disabled=False,
        add_host_gateway=True,
    )

    # Use the project virtualenv interpreter where httpx is installed
    result = run_in_container(["/app/.venv/bin/python", "-c", py], "", cfg, timeout=45.0)
    assert result.returncode == 0, (
        f"container exited {result.returncode}\nstderr: {result.stderr}"
    )
    stdout = (result.stdout or "").strip()
    assert stdout != "", "blank response from omlx"
    # First line is the HTTP status code
    lines = stdout.splitlines()
    assert lines[0] == "200", f"omlx returned HTTP {lines[0]}:\n{stdout}"
    # The remaining lines are the JSON body (may contain newlines)
    body_text = "\n".join(lines[1:]).strip()
    assert body_text != "", f"empty JSON body from omlx:\n{stdout}"
    try:
        body = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid JSON body from omlx: {exc}\n{body_text}") from exc
    # Must contain a non-empty choices array
    assert isinstance(body.get("choices"), list) and body["choices"], (
        f"no choices in omlx response or choices empty:\n{body_text}"
    )
    # Ensure first choice has non-empty content (OpenAI chat format)
    first = body["choices"][0]
    content = (
        ((first.get("message") or {}).get("content") or "")
        or first.get("text", "")
    )
    assert isinstance(content, str) and content.strip() != "", (
        f"empty content in first choice from omlx:\n{body_text}"
    )
    # Do not impose stylistic constraints; only ensure non-empty content
