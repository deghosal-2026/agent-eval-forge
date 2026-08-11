"""AdapterManifest — structured adapter metadata with digest for baseline binding.

An :class:`AdapterManifest` captures the identity, capabilities, schema
contract, and security posture of an adapter. The ``digest`` is a SHA-256 of
the canonical JSON serialization of all other fields, so baseline bindings can
detect when an adapter's config or contract has changed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AdapterManifest:
    """Structured metadata describing an adapter's identity and contract.

    Fields:
        name: Unique adapter identifier (e.g. "python_import").
        version: Adapter / package version string.
        capabilities: List of supported features (e.g. "env_isolation",
            "timeout", "cancellation", "stdin_stdout", "network_policy").
        input_schema: JSON Schema dict describing the adapter config.
        output_schema: JSON Schema dict describing the run envelope.
        tool_event_stream_version: Schema version string for the event stream
            (e.g. "evalforge.run_envelope.v1").
        writable_paths: Paths the adapter may write to (for sandbox policy).
        network_policy: Network access policy — "allow_none", "allow_list",
            or "allow_all".
        required_secrets: Names of required secrets (never values).
        digest: SHA-256 hex digest of the canonical JSON of all other fields.
    """

    name: str
    version: str
    capabilities: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    tool_event_stream_version: str = "evalforge.run_envelope.v1"
    writable_paths: list[str] = field(default_factory=list)
    network_policy: str = "allow_none"
    required_secrets: list[str] = field(default_factory=list)
    digest: str = ""

    def compute_digest(self) -> str:
        """Compute and return the SHA-256 hex digest of all fields except digest.

        Serialises all fields (except ``digest``) as sorted JSON, then returns
        the SHA-256 hex digest. The digest is *not* stored on the instance
        automatically — call :meth:`compute_digest` and assign to ``digest``
        explicitly, or use :meth:`to_dict`.
        """
        data = asdict(self)
        data.pop("digest", None)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict, computing the digest if needed.

        If ``digest`` is empty, it is computed and set before returning.
        """
        if not self.digest:
            self.digest = self.compute_digest()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdapterManifest:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        return cls(**data)
