"""``evalforge test`` — run scenario packs as tests with auto-discovery.

Discovers scenario pack YAML/JSON files in a directory (default ``scenarios/``),
loads each pack, and runs the full evaluation pipeline against an agent.
Results are aggregated into a single report.

The discovery pattern is ``scenarios/**/*.yaml``, ``scenarios/**/*.yml``,
and ``scenarios/**/*.json``. Packs are sorted by filename for deterministic
ordering.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from evalforge.cli.util import parse_agent_spec


def _discover_packs(scenarios_dir: str) -> list[Path]:
    """Discover scenario pack files in a directory.

    Searches for YAML/JSON files in the given directory, excluding the
    ``fixtures/`` subdirectory (which contains individual tool fixtures,
    not scenario packs). Results are sorted by filename for deterministic
    ordering.

    Args:
        scenarios_dir: Directory to search for pack files.

    Returns:
        Sorted list of discovered pack file paths.
    """
    base = Path(scenarios_dir)
    if not base.exists() or not base.is_dir():
        return []

    # Only discover files directly in the scenarios directory, not in
    # subdirectories like fixtures/ which contain individual tool fixtures.
    patterns = ["*.yaml", "*.yml", "*.json"]
    packs: set[Path] = set()
    for pattern in patterns:
        packs.update(base.glob(pattern))
    return sorted(packs)


# The test command group — registered as a subcommand of ``main``
test_group = click.Group(name="test", help="Run scenario packs as tests.")


@test_group.command("run")
@click.option(
    "--scenarios-dir",
    default="scenarios",
    show_default=True,
    help="Directory containing scenario pack files",
)
@click.option(
    "--agent", required=True,
    help="Agent spec (e.g. 'python:my_module.run' or './my_agent')",
)
@click.option(
    "--agent-function",
    default=None,
    help="Override function name for Python-import adapters (default: 'run')",
)
@click.option("--judge", default=None, help="Judge spec (e.g. 'openai:gpt-4o-mini' or 'mock')")
@click.option(
    "--output", default=".evalforge", show_default=True,
    help="Output directory for runs and artifacts",
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "markdown", "terminal", "github-actions"]),
    default="terminal",
    show_default=True,
)
@click.option("--tags", default=None, help="Comma-separated tag filter")
@click.option("--ci", is_flag=True, help="CI mode: JSON-only, structured exit codes")
def test_run(
    scenarios_dir: str,
    agent: str,
    agent_function: str | None,
    judge: str | None,
    output: str,
    output_format: str,
    tags: str | None,
    ci: bool,
) -> None:
    """Discover and run all scenario packs as tests.

    Scans the scenarios directory for pack files, runs each pack's scenarios
    against the specified agent, and aggregates all results into a single
    report.

    Args:
        scenarios_dir: Directory containing scenario pack YAML/JSON files.
        agent: Agent spec string (adapter:value).
        judge: Judge spec for LLM-as-judge scoring.
        output: Base output directory.
        output_format: Output rendering format.
        tags: Comma-separated tag filter.
        ci: CI mode flag (forces JSON output).

    Exits with:
        0 if all scenarios pass, 1 if any scenario or pack fails.
    """
    from evalforge.cli.formatter import OutputFormatter
    from evalforge.runner import Runner, generate_run_id
    from evalforge.scoring.engine import ScoringEngine

    if ci:
        output_format = "json"

    packs = _discover_packs(scenarios_dir)
    if not packs:
        click.echo(f"No scenario packs found in '{scenarios_dir}/'", err=True)
        raise SystemExit(1)

    agent_config = parse_agent_spec(agent)
    if agent_function:
        agent_config["function"] = agent_function
    tag_list = tags.split(",") if tags else None

    all_results: list[dict[str, Any]] = []
    total_passed = 0
    total_warned = 0
    total_failed = 0
    total_scenarios = 0
    all_safety_violations: list[str] = []

    import time

    start_ms = int(time.time() * 1000)

    for pack_path in packs:
        click.echo(f"  Pack: {pack_path}", err=True)
        try:
            runner = Runner(agent_config=agent_config, output_dir=output)
            runner.load_pack(str(pack_path))
            run_id = generate_run_id()
            artifacts = runner.run_all(tags=tag_list, run_id=run_id)
            engine = ScoringEngine(runner.pack)
            from evalforge.scoring.judge.client import JudgeClient

            judge_client: JudgeClient | None = None
            if judge:
                from evalforge.cli.run import _resolve_judge

                judge_client = _resolve_judge(judge)
            run_score = engine.score_run(artifacts, judge=judge_client)

            pack_meta = runner.pack.pack
            result = {
                "pack_path": str(pack_path),
                "pack_name": pack_meta.name,
                "pack_version": pack_meta.version,
                "run_id": run_id,
                "passed": run_score.totals["passed"],
                "warned": run_score.totals["warned"],
                "failed": run_score.totals["failed"],
                "exit_code": run_score.exit_code,
                "safety_violations": run_score.safety_violations,
            }
            all_results.append(result)
            total_passed += run_score.totals["passed"]
            total_warned += run_score.totals["warned"]
            total_failed += run_score.totals["failed"]
            total_scenarios += (
                run_score.totals["passed"]
                + run_score.totals["warned"]
                + run_score.totals["failed"]
            )
            all_safety_violations.extend(run_score.safety_violations)
        except Exception as e:
            click.echo(f"  Error processing {pack_path}: {e}", err=True)
            all_results.append({
                "pack_path": str(pack_path),
                "error": str(e),
                "exit_code": 1,
            })
            total_failed += 1

    duration_ms = int(time.time() * 1000) - start_ms

    summary = {
        "packs": len(packs),
        "total_scenarios": total_scenarios,
        "passed": total_passed,
        "warned": total_warned,
        "failed": total_failed,
        "duration_ms": duration_ms,
        "safety_violations": all_safety_violations,
        "results": all_results,
    }

    formatter = OutputFormatter(output_format)
    output_content = formatter.format_test_result(summary)
    if output_content:
        report_path = Path(f"{output}/test-report.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(output_content)

    import json

    with open(Path(f"{output}/test-report.json"), "w") as f:
        json.dump(summary, f, indent=2)

    click.echo(f"\nTest run complete: {len(packs)} packs, {total_scenarios} scenarios")
    click.echo(
        f"  Passed: {total_passed}, Warned: {total_warned}, Failed: {total_failed}"
    )
    if all_safety_violations:
        click.echo(f"  Safety violations: {', '.join(all_safety_violations)}")

    if total_failed > 0:
        raise SystemExit(1)
