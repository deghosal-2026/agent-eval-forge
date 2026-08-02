from __future__ import annotations

import json
from pathlib import Path

from evalforge.schema_version import SchemaRegistry, SchemaValidator

VALID_V0_1 = {
    "schema_version": "v0.1",
    "run_id": "run-001",
    "pack_name": "test-pack",
    "total_scenarios": 3,
    "passed": 2,
    "warned": 1,
    "failed": 0,
    "exit_code": 0,
}

VALID_V0_2 = {
    "schema_version": "v0.2",
    "run_id": "run-001",
    "pack_name": "test-pack",
    "total_scenarios": 3,
    "passed": 2,
    "warned": 1,
    "failed": 0,
    "exit_code": 0,
    "determinism": {
        "seed": 42,
        "reproducible": True,
        "freeze_time": True,
        "freeze_random": True,
    },
    "failure_taxonomy": {
        "categories": {
            "timeout": {"count": 1, "scenario_ids": ["sc-1"]},
            "safety_violation": {"count": 0, "scenario_ids": []},
        }
    },
    "benchmark": {
        "source_name": "swe-bench",
        "source_version": "1.0",
        "source_url": "https://example.com",
        "task_count": 100,
    },
    "provenance": {
        "pack_uri": "git+https://example.com/pack.git",
        "content_hash": "abc123",
        "generated_at": "2025-01-01T00:00:00Z",
        "evaluator_info": {
            "name": "evalforge",
            "version": "0.2.0",
        },
    },
}


class TestSchemaRegistry:
    def test_registers_and_retrieves_schema(self) -> None:
        registry = SchemaRegistry()
        registry.register("test-v1", "run-result-v0.1.json")
        schema = registry.get_schema("test-v1")
        assert schema is not None
        assert schema["title"] == "EvalForge Run Result"

    def test_registers_and_retrieves_custom_schema(self, tmp_path: Path) -> None:
        custom_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        schema_path = tmp_path / "custom.json"
        schema_path.write_text(json.dumps(custom_schema), encoding="utf-8")
        registry = SchemaRegistry()
        registry.register("custom-v1", str(schema_path))
        retrieved = registry.get_schema("custom-v1")
        assert retrieved == custom_schema

    def test_returns_none_for_unknown_version(self) -> None:
        registry = SchemaRegistry()
        assert registry.get_schema("nonexistent") is None

    def test_lists_versions(self) -> None:
        registry = SchemaRegistry()
        versions = registry.list_versions()
        assert "v0.1" in versions
        assert "v0.2" in versions
        assert versions == sorted(versions)

    def test_lists_versions_after_register(self) -> None:
        registry = SchemaRegistry()
        registry.register("test-v1", "run-result-v0.1.json")
        versions = registry.list_versions()
        assert "test-v1" in versions


class TestSchemaValidator:
    def test_detects_valid_v0_1_output(self) -> None:
        validator = SchemaValidator()
        result = validator.validate(VALID_V0_1, schema_version="v0.1")
        assert result.valid
        assert result.schema_version == "v0.1"
        assert len(result.errors) == 0

    def test_detects_valid_v0_2_output(self) -> None:
        validator = SchemaValidator()
        result = validator.validate(VALID_V0_2, schema_version="v0.2")
        assert result.valid
        assert result.schema_version == "v0.2"
        assert len(result.errors) == 0

    def test_detects_invalid_output_missing_required_fields(self) -> None:
        validator = SchemaValidator()
        result = validator.validate({"schema_version": "v0.1"}, schema_version="v0.1")
        assert not result.valid
        assert len(result.errors) > 0

    def test_reports_specific_errors(self) -> None:
        validator = SchemaValidator()
        result = validator.validate(
            {"schema_version": "v0.1", "run_id": "bad-run"},
            schema_version="v0.1",
        )
        assert not result.valid
        missing_fields = {
            "pack_name", "total_scenarios", "passed", "warned", "failed", "exit_code"
        }
        found_missing = set()
        for error in result.errors:
            for field in missing_fields:
                if field in error:
                    found_missing.add(field)
        assert len(found_missing) >= 2

    def test_autodetects_version_from_data(self) -> None:
        validator = SchemaValidator()
        result = validator.validate(VALID_V0_1)
        assert result.valid
        assert result.schema_version == "v0.1"

    def test_falls_back_to_current_version_when_not_in_data(self) -> None:
        validator = SchemaValidator()
        data_fallback = dict(VALID_V0_1)
        data_fallback.pop("schema_version")
        result = validator.validate(data_fallback)
        assert result.schema_version == "v0.2"

    def test_unknown_version_validation_fails_gracefully(self) -> None:
        validator = SchemaValidator()
        result = validator.validate(VALID_V0_1, schema_version="v9.9")
        assert not result.valid
        assert "Unknown schema version" in result.errors[0]

    def test_get_current_version(self) -> None:
        validator = SchemaValidator()
        assert validator.get_current_version() == "v0.2"


class TestMigrationCheck:
    def test_migration_check_between_v0_1_and_v0_2(self) -> None:
        registry = SchemaRegistry()
        changes = registry.check_migration("v0.1", "v0.2")
        assert len(changes) > 0
        assert any("determinism" in c for c in changes)
        assert any("failure_taxonomy" in c for c in changes)
        assert any("benchmark" in c for c in changes)
        assert any("provenance" in c for c in changes)

    def test_migration_check_no_differences(self) -> None:
        registry = SchemaRegistry()
        changes = registry.check_migration("v0.1", "v0.1")
        assert changes == []

    def test_migration_check_unknown_from_version(self) -> None:
        registry = SchemaRegistry()
        changes = registry.check_migration("v0.0", "v0.1")
        assert len(changes) == 1
        assert "from_version" in changes[0]

    def test_migration_check_unknown_to_version(self) -> None:
        registry = SchemaRegistry()
        changes = registry.check_migration("v0.1", "v0.0")
        assert len(changes) == 1
        assert "to_version" in changes[0]


class TestBackwardCompatibility:
    def test_v0_2_is_backward_compatible_with_v0_1(self) -> None:
        validator = SchemaValidator()
        assert validator.is_backward_compatible("v0.1", "v0.2")

    def test_backward_compatible_same_version(self) -> None:
        validator = SchemaValidator()
        assert validator.is_backward_compatible("v0.1", "v0.1")

    def test_unknown_old_version_not_compatible(self) -> None:
        validator = SchemaValidator()
        assert not validator.is_backward_compatible("v0.0", "v0.2")

    def test_unknown_new_version_not_compatible(self) -> None:
        validator = SchemaValidator()
        assert not validator.is_backward_compatible("v0.1", "v0.0")
