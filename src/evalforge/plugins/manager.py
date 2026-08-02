"""Plugin manager — discover, register, validate, and load plugins."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, ClassVar


@dataclass
class PluginInfo:
    """Metadata describing a registered plugin.

    Attributes:
        name: Unique plugin name.
        version: Plugin version string.
        type: One of ``"scorer"``, ``"adapter"``, ``"judge"``, or ``"benchmark"``.
        entry_point: Python entry point string (e.g. ``"my_package.module:class"``).
        description: Human-readable summary.
        author: Plugin author.
        dependencies: List of package dependency specifiers.
        source: Origin — one of ``"entry-point"`` or a file path.
    """
    name: str
    version: str
    type: str
    entry_point: str
    description: str = ""
    author: str = ""
    dependencies: list[str] = field(default_factory=list)
    source: str = "entry-point"


class PluginRegistry:
    """Central registry for all plugin types.

    Maintains separate maps for scorers, adapters, judges, and benchmark
    loaders, plus a metadata index keyed by plugin name.
    """

    def __init__(self) -> None:
        self._scorers: dict[str, type] = {}
        self._adapters: dict[str, type] = {}
        self._judges: dict[str, type] = {}
        self._benchmark_loaders: dict[str, Callable[..., Any]] = {}
        self._plugin_infos: dict[str, PluginInfo] = {}

    def register_scorer(self, name: str, scorer_class: type) -> None:
        """Register a scorer plugin class.

        Args:
            name: Plugin name.
            scorer_class: The scorer class.

        Raises:
            ValueError: If *name* is already registered.
        """
        if name in self._scorers:
            raise ValueError(f"Duplicate scorer plugin registration: {name}")
        self._scorers[name] = scorer_class

    def register_adapter(self, name: str, adapter_class: type) -> None:
        """Register an adapter plugin class.

        Args:
            name: Plugin name.
            adapter_class: The adapter class.

        Raises:
            ValueError: If *name* is already registered.
        """
        if name in self._adapters:
            raise ValueError(f"Duplicate adapter plugin registration: {name}")
        self._adapters[name] = adapter_class

    def register_judge(self, name: str, judge_class: type) -> None:
        """Register a judge plugin class.

        Args:
            name: Plugin name.
            judge_class: The judge class.

        Raises:
            ValueError: If *name* is already registered.
        """
        if name in self._judges:
            raise ValueError(f"Duplicate judge plugin registration: {name}")
        self._judges[name] = judge_class

    def register_benchmark_loader(self, name: str, loader_fn: Callable[..., Any]) -> None:
        """Register a benchmark loader function.

        Args:
            name: Plugin name.
            loader_fn: A callable that returns a benchmark/scenario set.

        Raises:
            ValueError: If *name* is already registered.
        """
        if name in self._benchmark_loaders:
            raise ValueError(f"Duplicate benchmark loader registration: {name}")
        self._benchmark_loaders[name] = loader_fn

    def get_scorer(self, name: str) -> type | None:
        """Look up a scorer plugin by name.

        Args:
            name: Plugin name.

        Returns:
            The scorer class, or ``None``.
        """
        return self._scorers.get(name)

    def get_adapter(self, name: str) -> type | None:
        """Look up an adapter plugin by name.

        Args:
            name: Plugin name.

        Returns:
            The adapter class, or ``None``.
        """
        return self._adapters.get(name)

    def get_judge(self, name: str) -> type | None:
        """Look up a judge plugin by name.

        Args:
            name: Plugin name.

        Returns:
            The judge class, or ``None``.
        """
        return self._judges.get(name)

    def get_benchmark_loader(self, name: str) -> Callable[..., Any] | None:
        """Look up a benchmark loader by name.

        Args:
            name: Plugin name.

        Returns:
            The loader callable, or ``None``.
        """
        return self._benchmark_loaders.get(name)

    def list_plugins(self, plugin_type: str | None = None) -> list[PluginInfo]:
        """List all registered plugins, optionally filtered by type.

        Args:
            plugin_type: If set, only return plugins of this type.

        Returns:
            Sorted list of :class:`PluginInfo`.
        """
        infos = list(self._plugin_infos.values())
        if plugin_type:
            infos = [i for i in infos if i.type == plugin_type]
        return sorted(infos, key=lambda i: i.name)

    def get_plugin(self, name: str) -> PluginInfo | None:
        """Look up plugin metadata by name.

        Args:
            name: Plugin name.

        Returns:
            :class:`PluginInfo` or ``None``.
        """
        return self._plugin_infos.get(name)

    def _register_info(self, info: PluginInfo) -> None:
        """Register plugin metadata (internal, no duplicate check bypass)."""
        if info.name in self._plugin_infos:
            raise ValueError(f"Duplicate plugin info registration: {info.name}")
        self._plugin_infos[info.name] = info

    def _has_plugin(self, name: str) -> bool:
        """Check if a plugin name is already registered."""
        return name in self._plugin_infos


class PluginManager:
    """Discovers and loads plugins from entry points and filesystem."""

    ENTRY_POINT_GROUPS: ClassVar[dict[str, str]] = {
        "evalforge.scorers": "scorer",
        "evalforge.adapters": "adapter",
        "evalforge.judges": "judge",
        "evalforge.benchmarks": "benchmark",
    }

    def __init__(self) -> None:
        self._registry = PluginRegistry()

    @property
    def registry(self) -> PluginRegistry:
        """Return the underlying :class:`PluginRegistry`."""
        return self._registry

    def discover_entry_points(self) -> None:
        """Scan installed packages for EvalForge plugin entry points."""
        for group, plugin_type in self.ENTRY_POINT_GROUPS.items():
            try:
                eps = entry_points(group=group)
            except Exception:  # noqa: S112
                continue
            for ep in eps:
                dist = ep.dist
                info = PluginInfo(
                    name=ep.name,
                    version=dist.version if dist else "0.0.0",
                    type=plugin_type,
                    entry_point=ep.value,
                    description="",
                    author=str(dist.metadata.get("Author", ""))  # type: ignore[attr-defined]
                    if dist and dist.metadata
                    else "",
                    source="entry-point",
                )
                if not self._registry._has_plugin(info.name):
                    self._registry._register_info(info)

    def discover_directory(self, path: str) -> None:
        """Scan a directory for plugin Python files and register them.

        Skips files whose names start with ``_``.

        Args:
            path: Filesystem path to a directory.

        Raises:
            ValueError: If *path* is not a directory.
        """
        p = Path(path)
        if not p.is_dir():
            raise ValueError(f"Not a directory: {path}")
        for py_file in sorted(p.rglob("*.py")):
            if py_file.name.startswith("_"):
                continue
            self._load_plugin_file(py_file)

    def _load_plugin_file(self, filepath: Path) -> None:
        """Load a single plugin file and register its exported type."""
        module_name = _module_name_from_path(filepath)
        spec = importlib.util.spec_from_file_location(module_name, filepath)  # type: ignore[attr-defined]
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)  # type: ignore[attr-defined]
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        plugin_info = getattr(module, "PLUGIN_INFO", None)
        if plugin_info is None or not isinstance(plugin_info, PluginInfo):
            return
        plugin_info.source = str(filepath)
        if not self._registry._has_plugin(plugin_info.name):
            self._registry._register_info(plugin_info)
            _register_module_objects(self._registry, module, plugin_info)

    def load_plugin(self, name: str) -> Any:
        """Load a plugin by name using its entry point.

        Args:
            name: Plugin name.

        Returns:
            The loaded plugin object (class or function).

        Raises:
            KeyError: If the plugin is not registered.
            ImportError: If the entry point cannot be resolved.
        """
        info = self._registry.get_plugin(name)
        if info is None:
            raise KeyError(f"Plugin not found: {name}")
        type_map: dict[str, str] = {
            "scorer": "evalforge.scorers",
            "adapter": "evalforge.adapters",
            "judge": "evalforge.judges",
            "benchmark": "evalforge.benchmarks",
        }
        group = type_map.get(info.type, "")
        eps: Any
        try:
            eps = entry_points(group=group)
        except Exception:
            eps = ()
        for ep in eps:
            if ep.name == name:
                return ep.load()
        raise ImportError(f"Cannot load plugin '{name}': entry point not resolvable")

    def validate_plugin(self, info: PluginInfo) -> list[str]:
        """Validate a plugin's metadata and ensure it can be loaded with the required interface.

        Args:
            info: :class:`PluginInfo` to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors: list[str] = []
        if not info.name or not info.name.strip():
            errors.append("Plugin name is empty")
        if not info.version:
            errors.append("Plugin version is empty")
        if info.type not in ("scorer", "adapter", "judge", "benchmark"):
            errors.append(f"Unknown plugin type: {info.type}")
        if not info.entry_point:
            errors.append("Plugin entry point is empty")
        required_ifaces = {
            "scorer": ("score",),
            "adapter": ("_invoke", "run"),
            "judge": ("evaluate",),
            "benchmark": ("load",),
        }
        try:
            obj = self.load_plugin(info.name)
        except Exception:
            errors.append(f"Cannot load plugin '{info.name}'")
        else:
            for method in required_ifaces.get(info.type, ()):
                if not hasattr(obj, method) or not callable(getattr(obj, method, None)):
                    errors.append(f"Plugin '{info.name}' missing required method: {method}")
        return errors

    def install_plugin(self, path_or_name: str) -> None:
        """Install a plugin from a directory path or PyPI package.

        If *path_or_name* points to an existing directory, it is discovered
        via :meth:`discover_directory`. Otherwise it is installed via pip.

        Args:
            path_or_name: Directory path or PyPI package name.
        """
        p = Path(path_or_name)
        if p.exists():
            self.discover_directory(path_or_name)
        else:
            import subprocess

            subprocess.check_call(  # noqa: S603
                [sys.executable, "-m", "pip", "install", path_or_name]
            )

    def list_plugins(self, plugin_type: str | None = None) -> list[PluginInfo]:
        """List all discovered plugins, optionally filtered by type.

        Args:
            plugin_type: Optional type filter.

        Returns:
            Sorted list of :class:`PluginInfo`.
        """
        return self._registry.list_plugins(plugin_type)

    def get_plugin(self, name: str) -> PluginInfo | None:
        """Look up plugin metadata by name.

        Args:
            name: Plugin name.

        Returns:
            :class:`PluginInfo` or ``None``.
        """
        return self._registry.get_plugin(name)


def discover_plugins() -> PluginManager:
    """Convenience function — create a :class:`PluginManager` and discover entry points.

    Returns:
        A fully initialised :class:`PluginManager`.
    """
    mgr = PluginManager()
    mgr.discover_entry_points()
    return mgr


def _register_module_objects(
    registry: PluginRegistry,
    module: Any,
    info: PluginInfo,
) -> None:
    """Register the exported class/function from a plugin module into the registry."""
    if info.type == "scorer":
        cls = getattr(module, "ScorerPlugin", None)
        if cls is not None and isinstance(cls, type):
            registry.register_scorer(info.name, cls)
    elif info.type == "adapter":
        cls = getattr(module, "AdapterPlugin", None)
        if cls is not None and isinstance(cls, type):
            registry.register_adapter(info.name, cls)
    elif info.type == "judge":
        cls = getattr(module, "JudgePlugin", None)
        if cls is not None and isinstance(cls, type):
            registry.register_judge(info.name, cls)
    elif info.type == "benchmark":
        fn = getattr(module, "load_benchmark", None)
        if fn is not None and callable(fn):
            registry.register_benchmark_loader(info.name, fn)


def _module_name_from_path(filepath: Path) -> str:
    """Derive a unique module name from a file path."""
    return f"evalforge.plugins.dynamic.{filepath.stem}"
