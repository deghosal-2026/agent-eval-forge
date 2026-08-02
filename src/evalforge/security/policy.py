"""Trust policy enforcement for scenario packs and agent adapters.

Defines a minimal policy matrix for pack trust levels → allowed adapter types
and sandbox requirements. This is a conservative v0 that can expand.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from evalforge.security.egress import EgressPolicy, EgressPolicyBuilder

# Logger for policy enforcement decisions. Used at INFO level when a policy
# evaluation occurs (via --explain-policy or during run/validate) so users can
# audit why a particular adapter/trust combination was allowed or denied.
logger = logging.getLogger("evalforge.security")

# Trust levels for scenario packs. Maps to the origin of the pack:
#   builtin  — ships with EvalForge, fully vetted
#   local    — authored by the user on the local filesystem
#   external — sourced from a remote registry or third-party
TrustLevel = Literal["builtin", "local", "external"]


@dataclass(frozen=True)
class TrustPolicy:
    """Policy for a specific trust-level / adapter-type combination.

    Attributes:
        trust: The pack's trust level (``builtin``, ``local``, or ``external``).
        adapter_type: The agent adapter type (e.g. ``"subprocess"``, ``"python"``).
        sandbox: Whether sandbox execution is required.
        egress: The egress policy to enforce for this combination.
    """

    trust: TrustLevel
    adapter_type: str
    sandbox: bool
    egress: EgressPolicy = field(default_factory=EgressPolicyBuilder.strict_production)

    def allowed(self) -> tuple[bool, str | None]:
        """Check whether this trust/adapter combination is allowed.

        Rules:
        - External packs may only use the subprocess adapter and require sandbox.
        - Local and builtin packs are always allowed.

        Returns:
            A tuple of ``(allowed, reason_if_denied)``.
        """
        t = self.trust
        a = self.adapter_type

        if t == "external":
            if a != "subprocess":
                return (
                    False,
                    "external packs may only use subprocess adapter (python/http disallowed)",
                )
            if not self.sandbox:
                return (False, "external packs require --sandbox enabled")
            return (True, None)

        if t == "local":
            return (True, None)

        if t == "builtin":
            return (True, None)

        return (False, f"unknown trust level: {t}")

    def to_config(self) -> dict[str, Any]:
        """Serialize trust policy into an adapter-compatible config dict.

        Returns:
            A dict with keys ``sandbox``, ``trust_level``, and ``egress_policy``
            suitable for passing to an agent adapter.
        """
        return {
            "sandbox": self.sandbox,
            "trust_level": self.trust,
            "egress_policy": {
                "allowed_domains": self.egress.allowed_domains,
                "blocked_domains": self.egress.blocked_domains,
                "allowed_ports": self.egress.allowed_ports,
                "allowed_schemes": self.egress.allowed_schemes,
                "allow_localhost": self.egress.allow_localhost,
                "allow_private_ips": self.egress.allow_private_ips,
            },
        }
