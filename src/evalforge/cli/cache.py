"""``evalforge cache`` — manage evaluation caches.

Provides commands for clearing cached data (run outputs, baselines, and
judge result caches) from the output directory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

cache_group = click.Group(
    name="cache",
    help="Manage evaluation caches.",
)


@cache_group.command("clear")
@click.option(
    "--output-dir",
    default=".evalforge",
    show_default=True,
    help="Output directory whose caches should be cleared",
)
def cache_clear(output_dir: str) -> None:
    """Clear all cached evaluation data.

    Removes the following subdirectories from the output directory:
    - ``runs/`` — all saved run results and scores
    - ``baselines/`` — all saved golden baselines
    - ``cache/`` — any cached judge results

    Use this to start fresh or reclaim disk space.
    """
    base = Path(output_dir)
    cleared = 0
    for subdir in ["runs", "baselines", "cache"]:
        path = base / subdir
        if path.exists():
            shutil.rmtree(path)
            cleared += 1
    click.echo(
        f"Cleared {cleared} cache director{'y' if cleared == 1 else 'ies'}"
        f" under {output_dir}/"
    )
