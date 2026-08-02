"""``evalforge plugins`` — discover, list, and inspect plugins.

Provides commands for managing EvalForge's plugin system, which supports
custom scorers, adapters, judges, and benchmark loaders registered via
entry points or directory discovery.
"""

from __future__ import annotations

import click

from evalforge.plugins.manager import PluginManager, discover_plugins


@click.group()
def plugins() -> None:
    """Manage EvalForge plugins (scorers, adapters, judges, benchmarks)."""


@plugins.command("list")
@click.option(
    "--type",
    "plugin_type",
    type=click.Choice(["scorer", "adapter", "judge", "benchmark"]),
    help="Filter by plugin type.",
)
def list_plugins(plugin_type: str | None) -> None:
    """List registered plugins.

    Displays all discovered plugins, optionally filtered by type.
    Each entry shows the plugin name, type, and version.

    Args:
        plugin_type: Optional filter to show only plugins of a specific type.
    """
    mgr = discover_plugins()
    infos = mgr.list_plugins(plugin_type)
    if not infos:
        click.echo("  (no plugins registered)")
        return
    if plugin_type:
        click.echo(f"Registered {plugin_type} plugins:")
    else:
        click.echo("Registered plugins:")
    for info in infos:
        click.echo(f"  {info.name:30s} {info.type:10s} v{info.version}")


@plugins.command()
@click.argument("name")
def info(name: str) -> None:
    """Show detailed information about a plugin.

    Displays the plugin's name, version, type, entry point, source
    location, description, author, and dependencies.

    Args:
        name: Plugin name to query.
    """
    mgr = discover_plugins()
    pinfo = mgr.get_plugin(name)
    if pinfo is None:
        click.echo(f"Plugin '{name}' not found.")
        raise SystemExit(1)
    click.echo(f"Name:        {pinfo.name}")
    click.echo(f"Version:     {pinfo.version}")
    click.echo(f"Type:        {pinfo.type}")
    click.echo(f"Entry point: {pinfo.entry_point}")
    click.echo(f"Source:      {pinfo.source}")
    if pinfo.description:
        click.echo(f"Description: {pinfo.description}")
    if pinfo.author:
        click.echo(f"Author:      {pinfo.author}")
    if pinfo.dependencies:
        click.echo(f"Dependencies: {', '.join(pinfo.dependencies)}")


@plugins.command()
@click.argument("path", default=".")
def discover(path: str) -> None:
    """Discover plugins from a directory.

    Scans the given directory for EvalForge plugin packages and
    registers them in the plugin manager.

    Args:
        path: Directory path to scan for plugins (default: current dir).
    """
    mgr = PluginManager()
    mgr.discover_entry_points()
    try:
        mgr.discover_directory(path)
    except ValueError as exc:
        click.echo(str(exc))
        raise SystemExit(1) from exc
    infos = mgr.list_plugins()
    if not infos:
        click.echo("No plugins discovered.")
        return
    click.echo(f"Discovered {len(infos)} plugin(s):")
    for info in infos:
        click.echo(f"  {info.name:30s} {info.type:10s} {info.source}")


@plugins.command()
@click.argument("target")
def install(target: str) -> None:
    """Install a plugin from a directory path or PyPI package name.

    Installs the plugin, then re-discovers all entry points to make
    the new plugin available.

    Args:
        target: Directory path or PyPI package name to install.
    """
    mgr = PluginManager()
    mgr.install_plugin(target)
    mgr.discover_entry_points()
    infos = mgr.list_plugins()
    click.echo(f"Installation complete. {len(infos)} plugin(s) available.")
