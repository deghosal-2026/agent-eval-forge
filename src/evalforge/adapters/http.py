"""HTTP adapter: POST the invocation payload to a local agent server.

The agent contract mirrors the subprocess adapter: the invocation payload is
sent as JSON in the request body, and the response body is parsed as a
``evalforge.run_envelope.v1`` envelope (with raw-text fallback unless
``strict_output`` is set). A non-200 response is an error.
"""

from __future__ import annotations

from typing import Any

import httpx

from evalforge.adapters.base import Adapter
from evalforge.models.errors import AdapterError, AgentTimeoutError


class HttpAdapter(Adapter):
    """Invoke an agent over HTTP POST."""

    name = "http"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str:
        url = config.get("url")
        if not url:
            raise AdapterError("http adapter requires `url` in config")
        timeout = float(config.get("timeout_seconds", 120))
        try:
            response = httpx.post(url, json=payload, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise AgentTimeoutError(f"agent exceeded {timeout}s timeout") from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"http request failed: {exc}") from exc

        if response.status_code != 200:
            raise AdapterError(
                f"agent returned HTTP {response.status_code}: {response.text[:200]}"
            )
        return response.text
