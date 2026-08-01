"""HTTP adapter: POST the invocation payload to a local agent server.

The agent contract mirrors the subprocess adapter: the invocation payload is
sent as JSON in the request body, and the response body is parsed as a
``evalforge.run_envelope.v1`` envelope (with raw-text fallback unless
``strict_output`` is set). A non-200 response is an error.

When sandbox is enabled, the target URL is checked against an optional
allowlist/denylist to enforce network egress policy. Matching is done on
the URL hostname (parsed via ``urllib.parse.urlparse``), not via raw substring
search, to prevent bypasses like ``http://127.0.0.1.evil.com``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from evalforge.adapters.base import Adapter
from evalforge.models.errors import AdapterError, AgentTimeoutError

# Default sets for sandboxed HTTP adapter.
# Users can override via config: ``sandbox_allowed_urls`` / ``sandbox_denied_urls``.
# The defaults restrict outbound HTTP to localhost only, preventing the agent
# from exfiltrating data to arbitrary external endpoints. This is a conservative
# v0 policy; users can widen the allowlist for agents that need to call real
# external APIs (e.g. retrieval, database lookups). The deny list takes priority
# over the allow list so a URL can be globally blocked even if it matches an
# allowed prefix.
_SANDBOX_ALLOWED_URLS: set[str] = {"http://localhost", "http://127.0.0.1"}
_SANDBOX_DENIED_URLS: set[str] = set()


def _parse_hostnames(urls: set[str]) -> set[str]:
    """Extract hostnames from a set of URLs, ignoring invalid entries.

    Accepts full URLs (``http://localhost:8080/path``) or bare hostnames.
    Returns only the hostname portion (e.g. ``localhost``, ``127.0.0.1``).
    Entries that cannot be parsed (missing scheme, malformed) are silently
    skipped so a misconfigured allowlist entry never silently allows all URLs.
    """
    hosts: set[str] = set()
    for u in urls:
        parsed = urlparse(u)
        if parsed.hostname:
            hosts.add(parsed.hostname)
    return hosts


class HttpAdapter(Adapter):
    """Invoke an agent over HTTP POST."""

    name = "http"

    def _invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> str:
        url = config.get("url")
        if not url:
            raise AdapterError("http adapter requires `url` in config")

        if config.get("sandbox"):
            allowed = set(config.get("sandbox_allowed_urls", _SANDBOX_ALLOWED_URLS))
            denied = set(config.get("sandbox_denied_urls", _SANDBOX_DENIED_URLS))
            # Parse hostname from the target URL — NOT substring matching,
            # which would allow bypass via ``http://127.0.0.1.evil.com``.
            # Using urlparse ensures we only compare the actual host portion.
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            if hostname == "":
                raise AdapterError("cannot parse hostname for sandbox check")

            # Denied check first: a URL in the denied set is always rejected,
            # even if it also matches the allowed set. This lets operators
            # block specific endpoints for compliance (e.g. block production
            # API in CI even though *.example.com is allowed).
            denied_hosts = _parse_hostnames(denied)
            if any(
                blocked_host == hostname or hostname.endswith("." + blocked_host)
                for blocked_host in denied_hosts
            ):
                raise AdapterError(
                    f"URL host '{hostname}' is denied in sandbox mode"
                )

            # Allow check: the hostname must be an exact match or a subdomain
            # of an allowed entry.localhost" matches both ``localhost`` and
            # ``api.localhost``, but ``evil127.0.0.1.com`` does NOT match
            # ``127.0.0.1`` because the dot prefix prevents false positives.
            allowed_hosts = _parse_hostnames(allowed)
            if not any(
                hostname == allowed_host or hostname.endswith("." + allowed_host)
                for allowed_host in allowed_hosts
            ):
                raise AdapterError(
                    f"URL host '{hostname}' is not in sandbox allowlist"
                    f" ({allowed_hosts or 'localhost only'})"
                )

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
