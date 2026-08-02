"""Tests for the plugin system — registry, manager, discovery, and CLI."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from evalforge.cli.__main__ import main
from evalforge.plugins.manager import (
    PluginInfo,
    PluginManager,
    PluginRegistry,
    discover_plugins,
)


class _FakeScorer:
    def score(self, artifact, scenario, metric_config):
        return {}


class _FakeAdapter:
    def _invoke(self, payload, config):
        return ""

    def run(self, scenario, config):
        return {}


class _FakeJudge:
    def evaluate(self, **kwargs):
        return {}


class _FakeBenchmarkLoader:
    pass


def _fake_load_benchmark():
    return {}


class TestPluginRegistry:
    def test_register_and_get_scorer(self) -> None:
        registry = PluginRegistry()
        registry.register_scorer("my_scorer", _FakeScorer)
        assert registry.get_scorer("my_scorer") is _FakeScorer

    def test_register_and_get_adapter(self) -> None:
        registry = PluginRegistry()
        registry.register_adapter("my_adapter", _FakeAdapter)
        assert registry.get_adapter("my_adapter") is _FakeAdapter

    def test_register_and_get_judge(self) -> None:
        registry = PluginRegistry()
        registry.register_judge("my_judge", _FakeJudge)
        assert registry.get_judge("my_judge") is _FakeJudge

    def test_register_and_get_benchmark_loader(self) -> None:
        registry = PluginRegistry()
        registry.register_benchmark_loader("my_bm", _fake_load_benchmark)
        assert registry.get_benchmark_loader("my_bm") is _fake_load_benchmark

    def test_duplicate_scorer_raises(self) -> None:
        registry = PluginRegistry()
        registry.register_scorer("dup", _FakeScorer)
        with pytest.raises(ValueError, match="Duplicate"):
            registry.register_scorer("dup", _FakeScorer)

    def test_duplicate_adapter_raises(self) -> None:
        registry = PluginRegistry()
        registry.register_adapter("dup", _FakeAdapter)
        with pytest.raises(ValueError, match="Duplicate"):
            registry.register_adapter("dup", _FakeAdapter)

    def test_duplicate_judge_raises(self) -> None:
        registry = PluginRegistry()
        registry.register_judge("dup", _FakeJudge)
        with pytest.raises(ValueError, match="Duplicate"):
            registry.register_judge("dup", _FakeJudge)

    def test_duplicate_benchmark_raises(self) -> None:
        registry = PluginRegistry()
        registry.register_benchmark_loader("dup", _fake_load_benchmark)
        with pytest.raises(ValueError, match="Duplicate"):
            registry.register_benchmark_loader("dup", _fake_load_benchmark)

    def test_get_nonexistent_returns_none(self) -> None:
        registry = PluginRegistry()
        assert registry.get_scorer("nope") is None
        assert registry.get_adapter("nope") is None
        assert registry.get_judge("nope") is None
        assert registry.get_benchmark_loader("nope") is None

    def test_plugin_info_fields(self) -> None:
        info = PluginInfo(
            name="test_plugin",
            version="1.0.0",
            type="scorer",
            entry_point="mypkg:TestScorer",
            description="A test plugin",
            author="Tester",
            dependencies=["pydantic>=2"],
        )
        assert info.name == "test_plugin"
        assert info.version == "1.0.0"
        assert info.type == "scorer"
        assert info.entry_point == "mypkg:TestScorer"
        assert info.description == "A test plugin"
        assert info.author == "Tester"
        assert info.dependencies == ["pydantic>=2"]

    def test_list_plugins_filters_by_type(self) -> None:
        registry = PluginRegistry()
        registry._register_info(
            PluginInfo(name="s1", version="1.0", type="scorer", entry_point="pkg:s1")
        )
        registry._register_info(
            PluginInfo(name="a1", version="1.0", type="adapter", entry_point="pkg:a1")
        )
        assert len(registry.list_plugins("scorer")) == 1
        assert len(registry.list_plugins("adapter")) == 1
        assert len(registry.list_plugins("benchmark")) == 0
        assert len(registry.list_plugins()) == 2

    def test_duplicate_plugin_info_raises(self) -> None:
        registry = PluginRegistry()
        registry._register_info(
            PluginInfo(name="dup", version="1.0", type="scorer", entry_point="pkg:d")
        )
        with pytest.raises(ValueError, match="Duplicate"):
            registry._register_info(
                PluginInfo(name="dup", version="1.0", type="scorer", entry_point="pkg:d")
            )


class TestPluginManager:
    def test_discover_plugins_returns_manager(self) -> None:
        mgr = discover_plugins()
        assert isinstance(mgr, PluginManager)

    def test_list_plugins_initially_empty(self) -> None:
        mgr = PluginManager()
        assert mgr.list_plugins() == []

    def test_validate_invalid_type(self) -> None:
        mgr = PluginManager()
        info = PluginInfo(name="bad", version="1.0", type="unknown", entry_point="pkg:x")
        mgr.registry._register_info(info)
        with patch.object(mgr, "load_plugin", return_value=_FakeScorer()):
            errors = mgr.validate_plugin(info)
            assert "Unknown plugin type" in errors[0]

    def test_validate_empty_name(self) -> None:
        mgr = PluginManager()
        info = PluginInfo(name="", version="1.0", type="scorer", entry_point="pkg:x")
        errors = mgr.validate_plugin(info)
        assert any("empty" in e.lower() for e in errors)

    def test_validate_missing_required_method(self) -> None:
        mgr = PluginManager()
        info = PluginInfo(name="bad", version="1.0", type="scorer", entry_point="pkg:x")
        mgr.registry._register_info(info)

        class _BadScorer:
            pass

        with patch.object(mgr, "load_plugin", return_value=_BadScorer()):
            errors = mgr.validate_plugin(info)
            assert any("missing required method" in e.lower() for e in errors)

    def test_validate_valid_scorer(self) -> None:
        mgr = PluginManager()
        info = PluginInfo(name="good", version="1.0", type="scorer", entry_point="pkg:x")
        mgr.registry._register_info(info)
        with patch.object(mgr, "load_plugin", return_value=_FakeScorer()):
            errors = mgr.validate_plugin(info)
            assert errors == []

    def test_validate_valid_adapter(self) -> None:
        mgr = PluginManager()
        info = PluginInfo(name="good", version="1.0", type="adapter", entry_point="pkg:x")
        mgr.registry._register_info(info)
        with patch.object(mgr, "load_plugin", return_value=_FakeAdapter()):
            errors = mgr.validate_plugin(info)
            assert errors == []

    def test_validate_valid_judge(self) -> None:
        mgr = PluginManager()
        info = PluginInfo(name="good", version="1.0", type="judge", entry_point="pkg:x")
        mgr.registry._register_info(info)
        with patch.object(mgr, "load_plugin", return_value=_FakeJudge()):
            errors = mgr.validate_plugin(info)
            assert errors == []

    def test_validate_benchmark_missing_loader(self) -> None:
        mgr = PluginManager()
        info = PluginInfo(name="bm", version="1.0", type="benchmark", entry_point="pkg:x")
        mgr.registry._register_info(info)
        with patch.object(mgr, "load_plugin", return_value=_FakeBenchmarkLoader()):
            errors = mgr.validate_plugin(info)
            assert any("missing required method" in e.lower() for e in errors)

    def test_validate_cannot_load(self) -> None:
        mgr = PluginManager()
        info = PluginInfo(name="gone", version="1.0", type="scorer", entry_point="pkg:x")
        mgr.registry._register_info(info)
        with patch.object(mgr, "load_plugin", side_effect=ImportError("bad")):
            errors = mgr.validate_plugin(info)
            assert any("cannot load" in e.lower() for e in errors)

    def test_get_plugin_nonexistent(self) -> None:
        mgr = PluginManager()
        assert mgr.get_plugin("nope") is None

    def test_discover_directory_not_exists(self) -> None:
        mgr = PluginManager()
        with pytest.raises(ValueError, match="Not a directory"):
            mgr.discover_directory("/nonexistent/path")

    def test_discover_directory_with_plugin_file(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "my_plugin.py"
        plugin_file.write_text(
            textwrap.dedent("""\
                from evalforge.plugins.manager import PluginInfo

                PLUGIN_INFO = PluginInfo(
                    name="dir_plugin",
                    version="0.1.0",
                    type="scorer",
                    entry_point="my_plugin:TestScorer",
                    description="Discovered plugin",
                )

                class ScorerPlugin:
                    def score(self, artifact, scenario, metric_config):
                        return {}
            """)
        )
        mgr = PluginManager()
        mgr.discover_directory(str(tmp_path))
        infos = mgr.list_plugins()
        assert len(infos) >= 1
        names = [i.name for i in infos]
        assert "dir_plugin" in names

    def test_scorer_plugin_registration_with_registry(self) -> None:
        registry = PluginRegistry()
        registry.register_scorer("my_s", _FakeScorer)
        registry._register_info(
            PluginInfo(
                name="my_s",
                version="1.0",
                type="scorer",
                entry_point="t:t",
                description="s",
            )
        )
        info = registry.get_plugin("my_s")
        assert info is not None
        assert info.type == "scorer"

    def test_adapter_plugin_registration_with_registry(self) -> None:
        registry = PluginRegistry()
        registry.register_adapter("my_a", _FakeAdapter)
        registry._register_info(
            PluginInfo(name="my_a", version="1.0", type="adapter", entry_point="t:t")
        )
        assert registry.get_plugin("my_a") is not None

    def test_multiple_plugins_list_returns_all(self) -> None:
        registry = PluginRegistry()
        for i in range(3):
            name = f"p{i}"
            registry._register_info(
                PluginInfo(
                    name=name,
                    version=f"0.{i}.0",
                    type="scorer",
                    entry_point=f"pkg:p{i}",
                )
            )
            registry.register_scorer(name, _FakeScorer)
        assert len(registry.list_plugins()) == 3

    def test_list_plugins_sorted_by_name(self) -> None:
        registry = PluginRegistry()
        registry._register_info(
            PluginInfo(name="c", version="1.0", type="scorer", entry_point="p:c")
        )
        registry._register_info(
            PluginInfo(name="a", version="1.0", type="scorer", entry_point="p:a")
        )
        registry._register_info(
            PluginInfo(name="b", version="1.0", type="scorer", entry_point="p:b")
        )
        names = [i.name for i in registry.list_plugins()]
        assert names == ["a", "b", "c"]


class TestPluginsCLI:
    def test_plugins_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["plugins", "--help"])
        assert result.exit_code == 0
        assert "Manage EvalForge plugins" in result.output

    def test_plugins_list_empty(self) -> None:
        with patch.object(PluginManager, "discover_entry_points"):
            runner = CliRunner()
            result = runner.invoke(main, ["plugins", "list"])
            assert result.exit_code == 0
            assert "no plugins registered" in result.output

    def test_plugins_info_not_found(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["plugins", "info", "nope"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_plugins_info_found(self) -> None:
        mgr = PluginManager()
        mgr.registry._register_info(
            PluginInfo(
                name="testp",
                version="2.0.0",
                type="scorer",
                entry_point="test:TestScorer",
                description="Test desc",
                author="Author",
                dependencies=["dep1"],
            )
        )
        with patch("evalforge.cli.plugins.discover_plugins", return_value=mgr):
            runner = CliRunner()
            result = runner.invoke(main, ["plugins", "info", "testp"])
            assert result.exit_code == 0
            assert "testp" in result.output
            assert "2.0.0" in result.output
            assert "scorer" in result.output
            assert "Test desc" in result.output
            assert "Author" in result.output

    def test_plugins_list_with_type_filter(self) -> None:
        mgr = PluginManager()
        mgr.registry._register_info(
            PluginInfo(name="s1", version="1.0", type="scorer", entry_point="p:s1")
        )
        mgr.registry._register_info(
            PluginInfo(name="a1", version="1.0", type="adapter", entry_point="p:a1")
        )
        with patch("evalforge.cli.plugins.discover_plugins", return_value=mgr):
            runner = CliRunner()
            result = runner.invoke(main, ["plugins", "list", "--type", "scorer"])
            assert result.exit_code == 0
            assert "s1" in result.output
            assert "a1" not in result.output

    def test_plugins_discover_invalid_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["plugins", "discover", "/nonexistent"])
        assert result.exit_code == 1
        assert "Not a directory" in result.output

    def test_plugins_discover_empty_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["plugins", "discover", str(tmp_path)])
        assert result.exit_code == 0

    def test_plugins_install_path(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "inst_plugin.py"
        plugin_file.write_text(
            textwrap.dedent("""\
                from evalforge.plugins.manager import PluginInfo

                PLUGIN_INFO = PluginInfo(
                    name="installed_p",
                    version="0.1.0",
                    type="scorer",
                    entry_point="inst_plugin:Test",
                    description="Installed test",
                )
            """)
        )
        runner = CliRunner()
        with patch.object(PluginManager, "discover_entry_points"):
            result = runner.invoke(main, ["plugins", "install", str(tmp_path)])
            assert result.exit_code == 0
            assert "Installation complete" in result.output
