"""Versioned JSON schema validation for evaluation run results.

Provides :class:`SchemaValidator` for validating run result data against
versioned JSON schemas, :class:`SchemaRegistry` for managing available
schema versions, and version-aware compatibility checks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field as dc_field
from enum import Enum
from pathlib import Path
from typing import Any


class SchemaVersion(Enum):
    """Supported schema versions for evaluation run results."""

    V0_1 = "v0.1"
    V0_2 = "v0.2"


@dataclass
class ValidationResult:
    """Result of a schema validation operation.

    Attributes:
        valid: Whether the data passed validation.
        schema_version: The schema version used for validation.
        errors: List of validation error messages.
        warnings: List of non-fatal warning messages (deprecated fields, etc.).
    """

    valid: bool
    schema_version: str
    errors: list[str] = dc_field(default_factory=list)
    warnings: list[str] = dc_field(default_factory=list)


class SchemaValidator:
    """Validates run result data against versioned JSON schemas.

    Loads JSON Schema files from the ``schemas/`` directory (located three
    levels up from this file) and supports version resolution, backward
    compatibility checking, and deprecation/unknown-field warnings.
    """

    def __init__(self) -> None:
        """Initialize the validator and load built-in schemas."""
        self._schemas_dir = Path(__file__).resolve().parents[3] / "schemas"
        self._schemas: dict[str, dict[str, Any]] = {}
        self._load_builtin_schemas()

    def _load_builtin_schemas(self) -> None:
        """Load all built-in JSON schemas from the schemas directory.

        Expects files named ``run-result-<version>.json`` (e.g.
        ``run-result-v0.1.json``, ``run-result-v0.2.json``).
        """
        for version in SchemaVersion:
            schema_path = self._schemas_dir / f"run-result-{version.value}.json"
            if schema_path.exists():
                self._schemas[version.value] = json.loads(
                    schema_path.read_text(encoding="utf-8")
                )

    def validate(
        self, data: dict[str, Any], schema_version: str | None = None
    ) -> ValidationResult:
        """Validate run result data against a schema version.

        Resolves the schema version from the provided parameter, the data's
        ``schema_version`` field, or defaults to the current version (v0.2).

        Args:
            data: The run result data dict to validate.
            schema_version: Explicit schema version string. If ``None``,
                the version is read from ``data.get("schema_version")``
                or falls back to :meth:`get_current_version`.

        Returns:
            A :class:`ValidationResult` with validation outcome.
        """
        resolved_version: str = (
            schema_version
            or data.get("schema_version")
            or self.get_current_version()
        )

        if resolved_version not in self._schemas:
            return ValidationResult(
                valid=False,
                schema_version=resolved_version,
                errors=[f"Unknown schema version: {resolved_version}"],
            )

        schema = self._schemas[resolved_version]
        errors: list[str] = []
        warnings: list[str] = []

        from jsonschema.validators import validator_for  # type: ignore[import-untyped]

        validator_cls = validator_for(schema)
        validator = validator_cls(schema)

        for error in validator.iter_errors(data):
            path = " -> ".join(str(p) for p in error.absolute_path) or "(root)"
            errors.append(f"{path}: {error.message}")

        self._check_deprecated_fields(data, resolved_version, warnings)
        self._check_unknown_fields(data, schema, warnings)

        return ValidationResult(
            valid=len(errors) == 0,
            schema_version=resolved_version,
            errors=errors,
            warnings=warnings,
        )

    def get_current_version(self) -> str:
        """Get the current (latest) schema version string.

        Returns:
            The string ``"v0.2"``.
        """
        return SchemaVersion.V0_2.value

    def is_backward_compatible(self, old_version: str, new_version: str) -> bool:
        """Check if a schema version is backward-compatible with an older one.

        A schema is backward-compatible if all required fields and properties
        from the old schema are also present in the new schema.

        Args:
            old_version: The older schema version string.
            new_version: The newer schema version string.

        Returns:
            True if the new schema is backward-compatible with the old one.
        """
        old_schema = self._schemas.get(old_version)
        new_schema = self._schemas.get(new_version)
        if old_schema is None or new_schema is None:
            return False
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))
        if not old_required.issubset(new_required):
            return False
        old_props = set(old_schema.get("properties", {}).keys())
        new_props = set(new_schema.get("properties", {}).keys())
        if not old_props.issubset(new_props):
            return False
        return True

    def _check_deprecated_fields(
        self, data: dict[str, Any], _version: str, warnings: list[str]
    ) -> None:
        """Check for deprecated fields in the data.

        Currently a no-op placeholder for future deprecation warnings.

        Args:
            data: The data dict to check.
            _version: The schema version (unused currently).
            warnings: List to append warning messages to.
        """
        pass

    def _check_unknown_fields(
        self, data: dict[str, Any], schema: dict[str, Any], warnings: list[str]
    ) -> None:
        """Check for unknown fields in the data.

        Currently a no-op placeholder for future strict-mode warnings.

        Args:
            data: The data dict to check.
            schema: The JSON schema dict (unused currently).
            warnings: List to append warning messages to.
        """
        pass


class SchemaRegistry:
    """Registry of available JSON schemas for run result validation.

    Provides schema loading, version registration, listing, and migration
    checking between schema versions.
    """

    def __init__(self) -> None:
        """Initialize the registry and load built-in schemas."""
        self._schemas_dir = Path(__file__).resolve().parents[3] / "schemas"
        self._schemas: dict[str, dict[str, Any]] = {}
        self._load_builtin()

    def _load_builtin(self) -> None:
        """Load built-in schemas from the schemas directory."""
        for version in SchemaVersion:
            schema_path = self._schemas_dir / f"run-result-{version.value}.json"
            if schema_path.exists():
                self._schemas[version.value] = json.loads(
                    schema_path.read_text(encoding="utf-8")
                )

    def register(self, version: str, schema_path: str) -> None:
        """Register a custom schema version from a file.

        Args:
            version: The version string to register.
            schema_path: Path to the JSON schema file (absolute or relative
                to the schemas directory).
        """
        path = Path(schema_path)
        if not path.is_absolute():
            path = self._schemas_dir / path
        self._schemas[version] = json.loads(path.read_text(encoding="utf-8"))

    def get_schema(self, version: str) -> dict[str, Any] | None:
        """Get the schema dict for a registered version.

        Args:
            version: The schema version string.

        Returns:
            The JSON schema dict, or ``None`` if not registered.
        """
        return self._schemas.get(version)

    def list_versions(self) -> list[str]:
        """List all registered schema versions.

        Returns:
            A sorted list of version strings.
        """
        return sorted(self._schemas.keys())

    def check_migration(self, from_version: str, to_version: str) -> list[str]:
        """Check what changes are needed to migrate between schema versions.

        Compares required fields and properties between two versions and
        reports additions and removals.

        Args:
            from_version: The source schema version.
            to_version: The target schema version.

        Returns:
            A list of human-readable change descriptions.
        """
        from_schema = self._schemas.get(from_version)
        to_schema = self._schemas.get(to_version)
        if from_schema is None:
            return [f"Unknown from_version: {from_version}"]
        if to_schema is None:
            return [f"Unknown to_version: {to_version}"]

        changes: list[str] = []

        from_required = set(from_schema.get("required", []))
        to_required = set(to_schema.get("required", []))
        from_props = set(from_schema.get("properties", {}).keys())
        to_props = set(to_schema.get("properties", {}).keys())

        added_required = to_required - from_required
        removed_required = from_required - to_required

        for req_field in added_required:
            changes.append(f"ADDED required field: {req_field}")
        for req_field in removed_required:
            changes.append(f"REMOVED required field: {req_field}")

        added_props = to_props - from_props
        removed_props = from_props - to_props

        for prop in sorted(added_props):
            changes.append(f"ADDED property: {prop}")
        for prop in sorted(removed_props):
            changes.append(f"REMOVED property: {prop}")

        return changes
