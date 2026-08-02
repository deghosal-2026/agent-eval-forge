"""``evalforge benchmark`` — import external benchmark datasets as scenario packs.

Provides the ability to import datasets from established benchmarks (e.g.,
SWE-bench, WebArena) and convert them into EvalForge scenario packs for
consistent evaluation and comparison.
"""

from __future__ import annotations

import click

from evalforge.benchmarks import BenchmarkLoader, BenchmarkRegistry


@click.group()
def benchmark() -> None:
    """Import external benchmark datasets as scenario packs."""


@benchmark.command("import")
@click.option(
    "--format",
    "format_name",
    type=click.Choice(["swe-bench", "webarena"]),
    required=True,
    help="Benchmark format to import.",
)
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help="Path to the benchmark dataset file.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, writable=True),
    required=True,
    help="Output path for the generated scenario pack YAML.",
)
@click.option(
    "--pack-name",
    default=None,
    help="Name for the generated scenario pack (default: auto-derived from format).",
)
def import_benchmark(
    format_name: str,
    input_path: str,
    output_path: str,
    pack_name: str | None,
) -> None:
    """Import a benchmark dataset and export it as an EvalForge scenario pack.

    Loads tasks from the specified benchmark format, converts them into
    EvalForge scenario objects, and writes them as a YAML scenario pack
    file ready for use with ``evalforge run``.

    Args:
        format_name: Benchmark format name (e.g. "swe-bench", "webarena").
        input_path: Path to the raw benchmark dataset file.
        output_path: Output path for the generated scenario pack YAML.
        pack_name: Optional name override for the generated pack.
    """
    loader = BenchmarkLoader()
    registry = BenchmarkRegistry()

    if pack_name is None:
        pack_name = f"{format_name}-import"

    try:
        tasks = registry.load(format_name, input_path)
        click.echo(f"Loaded {len(tasks)} tasks from {format_name} dataset")
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise click.Abort() from exc

    try:
        out = loader.export_pack(tasks, output_path, pack_name)
        click.echo(f"Exported scenario pack to {out}")
        click.echo(f"  Pack name: {pack_name}")
        click.echo(f"  Scenarios: {len(tasks)}")
        click.echo(f"  Run with: evalforge run --pack {out} --agent ...")
    except Exception as exc:
        click.echo(f"Export failed: {exc}", err=True)
        raise click.Abort() from exc
