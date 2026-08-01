"""Trust policy enforcement for scenario packs and agent adapters.

Defines a minimal policy matrix for pack trust levels → allowed adapter types
and sandbox requirements. This is a conservative v0 that can expand.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TrustLevel = Literal["builtin", "local", "external"]


@dataclass(frozen=True)
class TrustPolicy:
    trust: TrustLevel
    adapter_type: str
    sandbox: bool

    def allowed(self) -> tuple[bool, str | None]:
        """Return (allowed, reason_if_denied)."""
        t = self.trust
        a = self.adapter_type

        # External: only subprocess is allowed and sandbox must be enabled
        if t == "external":
            if a != "subprocess":
                return (
                    False,
                    "external packs may only use subprocess adapter (python/http disallowed)",
                )
            if not self.sandbox:
                return (False, "external packs require --sandbox enabled")
            return (True, None)

        # Local: allow subprocess/python/http; sandbox recommended but not required
        if t == "local":
            return (True, None)

        # Builtin: allow all adapters
        if t == "builtin":
            return (True, None)

        # Unknown trust → deny by default
        return (False, f"unknown trust level: {t}")
