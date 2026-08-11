"""Network egress policy for agent evaluation runs.

Defines an :class:`EgressPolicy` dataclass for specifying allow/block rules,
an :class:`EgressController` that checks URLs against those rules, and an
:class:`EgressPolicyBuilder` with factory methods for common profiles
(deny-all, allow-list, block-list, strict-production, development, air-gapped).
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse


@dataclass
class EgressPolicy:
    """Network egress policy configuration.

    Attributes:
        allowed_domains: Domains agents may connect to (empty = deny-all).
        blocked_domains: Domains always denied (overrides allowed_domains).
        allowed_ports: Ports agents may connect on.
        allowed_schemes: URL schemes permitted (e.g. ``["https"]``).
        allow_localhost: Whether ``localhost`` / loopback addresses are permitted.
        allow_private_ips: Whether RFC 1918 private IPs are permitted.
        log_all_requests: If True, every checked request is recorded in the
            controller's request log for audit.
    """

    allowed_domains: list[str] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=list)
    allowed_ports: list[int] = field(default_factory=lambda: [80, 443])
    allowed_schemes: list[str] = field(default_factory=lambda: ["https"])
    allow_localhost: bool = False
    allow_private_ips: bool = False
    log_all_requests: bool = True


class EgressController:
    """Evaluates URLs against an :class:`EgressPolicy`.

    Supports scheme, port, domain allow/block, localhost detection, and
    private-IP detection. Every check result is optionally logged for audit.
    """

    def __init__(self, policy: EgressPolicy | None = None):
        """Initialize the controller.

        Args:
            policy: The egress policy to enforce. Defaults to a deny-all policy.
        """
        self._policy = policy or EgressPolicy()
        self._request_log: list[dict[str, Any]] = []

    def check_url(self, url: str) -> tuple[bool, str]:
        """Check whether a URL is permitted by the policy.

        Evaluation order: scheme → port → blocked domains → localhost →
        private IP → allowed domains.

        Args:
            url: The fully-qualified URL to check.

        Returns:
            A tuple of ``(allowed: bool, reason: str)``.
        """
        scheme, host, port, _path = self.parse_url(url)

        if self._policy.allowed_schemes and scheme not in self._policy.allowed_schemes:
            return False, (
                f"scheme '{scheme}' is not allowed "
                f"(allowed: {self._policy.allowed_schemes})"
            )

        if self._policy.allowed_ports and port not in self._policy.allowed_ports:
            return False, f"port {port} is not allowed (allowed: {self._policy.allowed_ports})"

        for blocked in self._policy.blocked_domains:
            if host == blocked or host.endswith("." + blocked):
                return False, f"domain '{host}' is blocked"

        if self.is_localhost(host):
            if not self._policy.allow_localhost:
                return False, f"localhost access to '{host}' is not allowed"
            return True, "allowed (localhost)"

        if self.is_private_ip(host):
            if not self._policy.allow_private_ips:
                return False, f"private IP access to '{host}' is not allowed"
            return True, "allowed (private IP)"

        if not self._policy.allowed_domains:
            return False, "no domains are allowed by policy"

        for allowed in self._policy.allowed_domains:
            if host == allowed or host.endswith("." + allowed):
                return True, f"allowed (domain '{host}' matches '{allowed}')"

        return False, f"domain '{host}' is not in the allowlist"

    def check_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[bool, str]:
        """Check a full HTTP request against the egress policy.

        Delegates to :meth:`check_url` and logs the outcome.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Target URL.
            headers: Optional request headers (not yet used in policy evaluation).

        Returns:
            A tuple of ``(allowed: bool, reason: str)``.
        """
        allowed, reason = self.check_url(url)
        self.log_request(method, url, "allowed" if allowed else "blocked")
        return allowed, reason

    def log_request(self, method: str, url: str, status: str) -> None:
        """Record a request in the audit log.

        Args:
            method: HTTP method.
            url: Target URL.
            status: Outcome string (e.g. ``"allowed"``, ``"blocked"``).
        """
        if self._policy.log_all_requests:
            now = datetime.now(UTC).isoformat()
            self._request_log.append({
                "method": method,
                "url": url,
                "status": status,
                "timestamp": now,
            })

    def get_request_log(self) -> list[dict[str, Any]]:
        """Return a copy of the request audit log."""
        return list(self._request_log)

    def is_private_ip(self, host: str) -> bool:
        """Check if a hostname resolves to an RFC 1918 private IP.

        First attempts DNS resolution, then checks direct IP literal parsing.

        Args:
            host: Hostname or IP string.

        Returns:
            True if the host resolves to a private IP.
        """
        try:
            addr = socket.getaddrinfo(host, None)
            for _family, _type, _proto, _name, sockaddr in addr:
                ip = sockaddr[0]
                try:
                    ip_addr = ipaddress.ip_address(ip)
                    if ip_addr.is_private:
                        return True
                except ValueError:
                    continue
        except socket.gaierror:
            pass

        try:
            ip_addr = ipaddress.ip_address(host)
            return ip_addr.is_private
        except ValueError:
            pass

        return False

    def is_localhost(self, host: str) -> bool:
        """Check if a hostname refers to the local machine.

        Detects common localhost aliases, ``.localhost`` / ``.local`` TLDs,
        and loopback IP addresses.

        Args:
            host: Hostname or IP string.

        Returns:
            True if the host is localhost.
        """
        if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):  # noqa: S104
            return True
        if host.endswith(".localhost") or host.endswith(".local"):
            return True
        try:
            ip_addr = ipaddress.ip_address(host)
            return ip_addr.is_loopback
        except ValueError:
            pass
        return False

    @staticmethod
    def parse_url(url: str) -> tuple[str, str, int, str]:
        """Parse a URL into its components with sensible defaults.

        Args:
            url: The URL string to parse.

        Returns:
            A tuple of ``(scheme, host, port, path)``. Scheme defaults to
            ``"https"``, port defaults to 443 for https or 80 for http.
        """
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        host = parsed.hostname or ""
        port = parsed.port
        if port is None:
            port = 443 if scheme == "https" else 80
        path = parsed.path or "/"
        return scheme, host, port, path


class EgressPolicyBuilder:
    """Factory for common :class:`EgressPolicy` profiles."""

    DEFAULT_DENY_ALL = EgressPolicy(
        allowed_domains=[],
        allowed_ports=[],
        allowed_schemes=[],
        allow_localhost=False,
        allow_private_ips=False,
    )

    @staticmethod
    def allow_list(domains: list[str]) -> EgressPolicy:
        """Build a policy that only allows the given domains on standard ports.

        Args:
            domains: List of allowed domain names.

        Returns:
            An :class:`EgressPolicy` with the given allowlist.
        """
        return EgressPolicy(allowed_domains=list(domains))

    @staticmethod
    def block_list(domains: list[str]) -> EgressPolicy:
        """Build a policy that blocks specific domains but allows everything else.

        Permits http/https on ports 80, 443, 8080, 8443.

        Args:
            domains: List of domains to block.

        Returns:
            An :class:`EgressPolicy` with the given blocklist.
        """
        return EgressPolicy(
            allowed_domains=["*"],
            blocked_domains=list(domains),
            allowed_ports=[80, 443, 8080, 8443],
            allowed_schemes=["http", "https"],
        )

    @staticmethod
    def strict_production() -> EgressPolicy:
        """Build a strict production policy.

        HTTPS-only, port 443 only, no localhost, no private IPs, no domains
        allowed (deny-all by default).

        Returns:
            An :class:`EgressPolicy` suitable for production environments.
        """
        return EgressPolicy(
            allowed_domains=[],
            blocked_domains=[],
            allowed_ports=[443],
            allowed_schemes=["https"],
            allow_localhost=False,
            allow_private_ips=False,
        )

    @staticmethod
    def development() -> EgressPolicy:
        """Build a permissive development policy.

        Allows http/https on a wide range of ports, localhost, and private IPs.

        Returns:
            An :class:`EgressPolicy` suitable for local development.
        """
        return EgressPolicy(
            allowed_domains=["*"],
            blocked_domains=[],
            allowed_ports=[80, 443, 8080, 8443, 3000, 5000, 8000],
            allowed_schemes=["http", "https"],
            allow_localhost=True,
            allow_private_ips=True,
        )

    @staticmethod
    def air_gapped() -> EgressPolicy:
        """Build an air-gapped policy that denies all network traffic.

        Returns:
            An :class:`EgressPolicy` that blocks all egress.
        """
        return EgressPolicy(
            allowed_domains=[],
            blocked_domains=[],
            allowed_ports=[],
            allowed_schemes=[],
            allow_localhost=False,
            allow_private_ips=False,
        )
