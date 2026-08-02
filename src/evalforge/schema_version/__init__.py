"""Schema version management for evaluation run results.

Provides versioned JSON schema validation and migration support for
evaluation run result files. Currently supports schema versions
``v0.1`` and ``v0.2``.
"""

from evalforge.schema_version.validator import (
    SchemaRegistry,
    SchemaValidator,
    SchemaVersion,
    ValidationResult,
)

__all__ = [
    "SchemaRegistry",
    "SchemaValidator",
    "SchemaVersion",
    "ValidationResult",
]
