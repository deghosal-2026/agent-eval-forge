"""``evalforge cache`` — manage evaluation caches.

Provides commands for clearing cached data (run outputs, baselines, and
judge result caches) from the output directory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

# The cache command group — registered as a subcommand of ``main``
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
@click.option(
    "--cache-type",
    type=click.Choice(["all", "judge", "runs", "baselines"]),
    default="all",
    help="Which cache type to clear",
)
def cache_clear(output_dir: str, cache_type: str) -> None:
    """Clear evaluation caches.

    Removes the specified cache subdirectories from the output directory.

    Args:
        output_dir: Base output directory whose caches should be cleared.
        cache_type: Which cache type to clear (all, judge, runs, or baselines).
    """
    base = Path(output_dir)
    cleared = 0
    # Map cache types to their corresponding subdirectory names
    targets = {
        "all": ["runs", "baselines", "judge_cache", "cache"],
        "judge": ["judge_cache", "cache"],
        "runs": ["runs"],
        "baselines": ["baselines"],
    }[cache_type]
    for subdir in targets:
        path = base / subdir
        if path.exists():
            shutil.rmtree(path)
            cleared += 1
    click.echo(
        f"Cleared {cleared} cache director{'ies' if cleared != 1 else 'y'}"
        f" under {output_dir}/"
    )


@cache_group.command("stats")
@click.option("--output-dir", default=".evalforge", show_default=True)
def cache_stats(output_dir: str) -> None:
    """Show judge cache statistics.

    Displays the number of cached files and total cache size in bytes.

    Args:
        output_dir: Base output directory containing the judge cache.
    """
    from evalforge.cache import JudgeCache

    jc = JudgeCache(base_dir=output_dir)
    s = jc.stats()
    click.echo(f"Judge cache: {s['files']} files, {s['size_bytes']} bytes")
