"""Tests for external benchmark loading and conversion."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from evalforge.benchmarks import BenchmarkLoader, BenchmarkRegistry, BenchmarkTask
from evalforge.models.pack import ScenarioPack

FIXTURES = Path(__file__).parent / "fixtures"

SWE_BENCH_PATH = FIXTURES / "sample_swe_bench.jsonl"
WEBARENA_PATH = FIXTURES / "sample_webarena.json"


class TestSweBenchLoading:
    def test_load_swe_bench_tasks(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_swe_bench(SWE_BENCH_PATH)
        assert len(tasks) == 3
        assert all(isinstance(t, BenchmarkTask) for t in tasks)

    def test_swe_bench_task_fields(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_swe_bench(SWE_BENCH_PATH)
        t0 = tasks[0]
        assert t0.task_id == "swe-1"
        assert t0.category == "swe-bench"
        assert "test/repo" in t0.prompt
        assert "Fix bug in calculator" in t0.prompt
        assert t0.expected["type"] == "exact"
        assert len(t0.tools) == 3

    def test_swe_bench_optional_fields(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_swe_bench(SWE_BENCH_PATH)
        t2 = tasks[2]
        assert t2.expected.get("hints_text") == "Look at the visitor pattern"
        assert t2.expected.get("fail_to_pass") == ["test_parse_1", "test_parse_2"]
        assert t2.expected.get("pass_to_pass") == ["test_format_1"]

    def test_swe_bench_tool_names(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_swe_bench(SWE_BENCH_PATH)
        tool_names = {t["name"] for t in tasks[0].tools}
        assert tool_names == {"read_file", "write_file", "execute_command"}


class TestWebArenaLoading:
    def test_load_webarena_tasks(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_webarena(WEBARENA_PATH)
        assert len(tasks) == 2
        assert all(isinstance(t, BenchmarkTask) for t in tasks)

    def test_webarena_task_fields(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_webarena(WEBARENA_PATH)
        t0 = tasks[0]
        assert t0.task_id == "wa-1"
        assert t0.category == "webarena"
        assert "Find a red laptop under $1000" in t0.prompt
        assert t0.expected == {"product_name": "Red Laptop", "price_max": 1000}

    def test_webarena_tool_names(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_webarena(WEBARENA_PATH)
        tool_names = {t["name"] for t in tasks[0].tools}
        assert "navigate" in tool_names
        assert "click" in tool_names
        assert "type" in tool_names
        assert "extract" in tool_names


class TestConversion:
    def test_convert_swe_to_pack(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_swe_bench(SWE_BENCH_PATH)
        pack = loader.convert_to_pack(tasks, "test-swe-pack")
        assert isinstance(pack, ScenarioPack)
        assert pack.pack.name == "test-swe-pack"
        assert pack.pack.version == "1.0.0"
        assert pack.pack.trust == "external"
        assert len(pack.scenarios) == 3

    def test_convert_webarena_to_pack(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_webarena(WEBARENA_PATH)
        pack = loader.convert_to_pack(tasks, "test-wa-pack")
        assert len(pack.scenarios) == 2
        assert pack.scenarios[0].id == "wa-1"
        assert pack.scenarios[0].tags == ["webarena"]

    def test_converted_scenario_structure(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_swe_bench(SWE_BENCH_PATH)
        pack = loader.convert_to_pack(tasks, "test-pack")
        s0 = pack.scenarios[0]
        assert s0.id == "swe-1"
        assert s0.title is not None
        assert s0.input == tasks[0].prompt
        assert s0.expected is not None
        assert s0.expected.type == "exact"
        assert len(s0.allowed_tools) == 3
        assert s0.tags == ["swe-bench"]
        assert "output_correctness" in s0.metrics
        assert "tool_correctness" in s0.metrics
        assert "task_completion" in s0.metrics

    def test_category_tagging(self) -> None:
        loader = BenchmarkLoader()
        swe_tasks = loader.load_swe_bench(SWE_BENCH_PATH)
        wa_tasks = loader.load_webarena(WEBARENA_PATH)
        swe_pack = loader.convert_to_pack(swe_tasks, "swe")
        wa_pack = loader.convert_to_pack(wa_tasks, "wa")
        assert all("swe-bench" in s.tags for s in swe_pack.scenarios)
        assert all("webarena" in s.tags for s in wa_pack.scenarios)

    def test_tool_generation_from_swe_bench(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_swe_bench(SWE_BENCH_PATH)
        pack = loader.convert_to_pack(tasks, "tools-test")
        s0 = pack.scenarios[0]
        tool_names = {t.name for t in s0.allowed_tools}
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "execute_command" in tool_names
        ws_tool = next(t for t in s0.allowed_tools if t.name == "write_file")
        assert ws_tool.description is not None

    def test_tool_generation_from_webarena(self) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_webarena(WEBARENA_PATH)
        pack = loader.convert_to_pack(tasks, "wa-tools-test")
        s0 = pack.scenarios[0]
        tool_names = {t.name for t in s0.allowed_tools}
        assert tool_names == {"navigate", "click", "type", "extract"}


class TestExport:
    def test_export_pack_yaml(self, tmp_path: Path) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_swe_bench(SWE_BENCH_PATH)
        out = tmp_path / "exported_pack.yaml"
        result = loader.export_pack(tasks, out, "exported")
        assert result == out
        assert out.exists()
        raw = out.read_text(encoding="utf-8")
        assert "pack:" in raw
        assert "exported" in raw
        assert "swe-1" in raw

    def test_export_roundtrip(self, tmp_path: Path) -> None:
        loader = BenchmarkLoader()
        tasks = loader.load_swe_bench(SWE_BENCH_PATH)
        out = tmp_path / "roundtrip.yaml"
        loader.export_pack(tasks, out, "roundtrip")
        packed = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert isinstance(packed, dict)
        assert packed["pack"]["name"] == "roundtrip"
        assert len(packed["scenarios"]) == 3


class TestBenchmarkRegistry:
    def test_load_via_registry(self) -> None:
        registry = BenchmarkRegistry()
        tasks = registry.load("swe-bench", str(SWE_BENCH_PATH))
        assert len(tasks) == 3
        assert tasks[0].category == "swe-bench"

    def test_webarena_via_registry(self) -> None:
        registry = BenchmarkRegistry()
        tasks = registry.load("webarena", str(WEBARENA_PATH))
        assert len(tasks) == 2
        assert tasks[0].category == "webarena"

    def test_register_and_load_custom(self) -> None:
        registry = BenchmarkRegistry()

        def custom_loader(path: str) -> list[BenchmarkTask]:
            return [
                BenchmarkTask(
                    task_id="custom-1",
                    category="custom",
                    prompt="Custom task",
                    expected={"type": "exact", "value": "ok"},
                    tools=[{"name": "probe"}],
                )
            ]

        registry.register("custom-format", custom_loader)
        tasks = registry.load("custom-format", "any/path")
        assert len(tasks) == 1
        assert tasks[0].task_id == "custom-1"
        assert tasks[0].category == "custom"

    def test_unknown_format_raises(self) -> None:
        registry = BenchmarkRegistry()
        with pytest.raises(ValueError, match="Unknown benchmark format"):
            registry.load("nonexistent", "some/path")


class TestErrorHandling:
    def test_missing_swe_bench_file(self) -> None:
        loader = BenchmarkLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_swe_bench(FIXTURES / "nope.jsonl")

    def test_missing_webarena_file(self) -> None:
        loader = BenchmarkLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_webarena(FIXTURES / "nope.json")

    def test_invalid_jsonl_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.jsonl"
        bad_file.write_text("not json\n", encoding="utf-8")
        loader = BenchmarkLoader()
        with pytest.raises(Exception):
            loader.load_swe_bench(bad_file)

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{broken", encoding="utf-8")
        loader = BenchmarkLoader()
        with pytest.raises(Exception):
            loader.load_webarena(bad_file)

    def test_empty_swe_bench_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        loader = BenchmarkLoader()
        tasks = loader.load_swe_bench(empty)
        assert tasks == []

    def test_empty_webarena_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.json"
        empty.write_text("[]", encoding="utf-8")
        loader = BenchmarkLoader()
        tasks = loader.load_webarena(empty)
        assert tasks == []

    def test_webarena_not_array_raises(self, tmp_path: Path) -> None:
        obj_file = tmp_path / "obj.json"
        obj_file.write_text('{"not": "an array"}', encoding="utf-8")
        loader = BenchmarkLoader()
        with pytest.raises(Exception, match="JSON array"):
            loader.load_webarena(obj_file)

    def test_duplicate_task_ids_in_conversion_raises(self) -> None:
        loader = BenchmarkLoader()
        dup = BenchmarkTask(
            task_id="same",
            category="test",
            prompt="ok",
            expected={"type": "exact", "value": "x"},
            tools=[],
        )
        with pytest.raises(ValueError, match="Duplicate"):
            loader.convert_to_pack([dup, dup], "dup-pack")

    def test_sanitize_scenario_id(self) -> None:
        assert BenchmarkLoader._sanitize_scenario_id("swe-1") == "swe-1"
        assert BenchmarkLoader._sanitize_scenario_id("a.b/c:d") == "a-b-c-d"
        assert BenchmarkLoader._sanitize_scenario_id("!!!") == "unknown"
