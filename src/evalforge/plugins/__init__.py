"""Plugin system — discover, register, and load plugins.

Exports PluginManager, PluginRegistry, and the top-level discover_plugins
convenience function.
"""

from __future__ import annotations

from evalforge.plugins.manager import PluginInfo, PluginManager, PluginRegistry, discover_plugins

__all__ = [
    "PluginInfo",
    "PluginManager",
    "PluginRegistry",
    "discover_plugins",
]
