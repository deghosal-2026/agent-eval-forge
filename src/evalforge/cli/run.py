r"""``evalforge run`` — run a scenario pack against an agent and score the results.

This is the primary entry point for end-to-end evaluation. It orchestrates
the full pipeline:

1. **Parse** the scenario pack YAML/JSON into ``ScenarioPack`` models.
2. **Invoke** each scenario against the agent via the configured adapter.
3. **Capture** normalized ``RunArtifact``\ s to ``.evalforge/runs/<run_id>/``.
4. **Score** each artifact against the scenario's expected behavior using
   deterministic scorers and an optional LLM-as-judge.
5. **Compare** (optional) against a saved golden baseline and produce a delta
   report.
6. **Report** in JSON (default), Markdown, or terminal (Rich) format.

All imports from the core library are deferred to function scope so that
``evalforge --help`` and ``evalforge run --help`` stay fast and never trigger
optional-dependency failures (e.g., missing ``rich`` or LLM SDKs).
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from evalforge.cli.util import parse_agent_spec
from evalforge.scoring.judge.client import JudgeClient


def _resolve_judge(judge_spec: str | None) -> JudgeClient | None:
    """Parse a judge spec like ``openai:gpt-4o-mini`` into a ``JudgeClient``.

    Supported providers:

    ========= ============= ============================================
    Provider  Default model Environment variable
    ========= ============= ============================================
    openai    gpt-4o-mini   ``OPENAI_API_KEY`` (required)
    anthropic claude-3-haiku ``ANTHROPIC_API_KEY`` (required)
    ollama    llama3        (local — no key needed)
    mock      —             Returns ``MockJudge(score=1.0)``
    ========= ============= ============================================

    Args:
        judge_spec: The judge spec string (e.g. ``"openai:gpt-4o-mini"``,
            ``"mock"``, or ``None`` to skip LLM judging).

    Returns:
        A configured ``JudgeClient`` instance, or ``None`` if no judge is
        requested.

    Raises:
        click.UsageError: If a required API key is not set.
        click.BadParameter: If the provider is unknown.
    """
    if judge_spec is None:
        return None

    import os

    parts = judge_spec.split(":", 1)
    provider = parts[0]
    model = parts[1] if len(parts) > 1 else None

    if provider == "openai":
        from evalforge.scoring.judge.openai import OpenAIClient

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise click.UsageError(
                "OPENAI_API_KEY environment variable not set "
                "(needed for openai judge)"
            )
        return OpenAIClient(api_key=api_key, model=model or "gpt-4o-mini")

    elif provider == "anthropic":
        from evalforge.scoring.judge.anthropic import AnthropicClient

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise click.UsageError(
                "ANTHROPIC_API_KEY environment variable not set "
                "(needed for anthropic judge)"
            )
        return AnthropicClient(api_key=api_key, model=model or "claude-3-haiku-20240307")

    elif provider == "ollama":
        from evalforge.scoring.judge.ollama import OllamaClient

        return OllamaClient(model=model or "llama3")

    elif provider == "mock":
        from evalforge.scoring.judge.mock import MockJudge

        return MockJudge(score=1.0)

    else:
        raise click.BadParameter(f"unknown judge provider: {provider}")


@click.command()
@click.option(
    "--pack",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the scenario pack YAML/JSON file",
)
@click.option(
    "--agent",
    required=True,
    help="Agent spec (e.g. 'python:my_module.run' or './my_agent' for subprocess)",
)
@click.option("--baseline", default=None, help="Optional baseline name for regression comparison")
@click.option("--judge", default=None, help="Judge spec (e.g. 'openai:gpt-4o-mini' or 'mock')")
@click.option(
    "--output", default=".evalforge", show_default=True,
    help="Output directory for runs and artifacts",
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "markdown", "terminal"]),
    default="json",
    show_default=True,
    help="Output format for the run report",
)
@click.option("--tags", default=None, help="Comma-separated tag filter (e.g. 'retrieval,safety')")
@click.option(
    "--workers",
    default=1,
    type=int,
    show_default=True,
    help="Number of parallel workers (1 = serial execution)",
)
@click.option(
    "--timeout",
    default=120,
    type=int,
    show_default=True,
    help="Per-scenario timeout in seconds",
)
@click.option("--ci", is_flag=True, help="CI mode: JSON-only output, structured exit codes")
@click.option(
    "--fixtures",
    is_flag=True,
    default=None,
    help="Run with fixtures (deterministic mode, no live tool calls)",
)
@click.option(
    "--live",
    is_flag=True,
    default=None,
    help="Run with live tool calls (disable fixtures)",
)
@click.option(
    "--fixtures-dir",
    default="scenarios/fixtures",
    show_default=True,
    help="Directory containing fixture JSON files",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable judge result caching",
)
@click.option(
    "--sandbox",
    is_flag=True,
    help="Run in sandbox mode (restricted env, no API key passthrough)",
)
@click.option(
    "--trust",
    type=click.Choice(["builtin", "local", "external"]),
    default=None,
    help="Override pack trust level",
)
@click.option(
    "--explain-policy",
    is_flag=True,
    help="Explain why the current adapter/trust combo is or isn't allowed",
)
def run(
    pack: str,
    agent: str,
    baseline: str | None,
    judge: str | None,
    output: str,
    output_format: str,
    tags: str | None,
    workers: int,
    timeout: int,
    ci: bool,
    fixtures: bool | None,
    fixtures_dir: str,
    no_cache: bool,
    sandbox: bool,
    trust: str | None,
    live: bool | None,
    explain_policy: bool = False,
) -> None:
    """Run a scenario pack against an agent, score results, and optionally compare.

    This is the primary EvalForge workflow: load scenarios, invoke the agent,
    score the results, and produce a report. If ``--baseline`` is provided the
    candidate run is compared against the golden baseline for regression detection.
    """
    # Core library imports deferred so --help is fast and optional dependencies
    # (rich, openai, anthropic) are only loaded when actually used.
    from evalforge.cli.formatter import OutputFormatter
    from evalforge.runner import Runner, generate_run_id
    from evalforge.scoring.engine import ScoringEngine

    # CI mode forces JSON output (machine-readable, no prompts)
    if ci:
        output_format = "json"

    if fixtures is not None and live is not None:
        raise click.UsageError("--fixtures and --live are mutually exclusive")

    # Parse the agent spec and extend with CLI-level overrides
    agent_config = parse_agent_spec(agent)
    agent_config["timeout_seconds"] = timeout
    if fixtures is not None:
        agent_config["fixtures"] = fixtures
    if live is not None:
        agent_config["fixtures"] = not live
    agent_config["fixtures_dir"] = fixtures_dir
    agent_config["sandbox"] = sandbox

    # Parse the optional tag filter
    tag_list = tags.split(",") if tags else None

    # Step 1: Load pack and create runner
    runner = Runner(agent_config=agent_config, output_dir=output)
    runner.load_pack(pack)

    if trust:
        runner.pack.pack.trust = trust

    # Enforce trust policy before running
    from evalforge.security.policy import TrustLevel, TrustPolicy
    pack_trust: TrustLevel = runner.pack.pack.trust  # type: ignore[assignment]
    agent_type = agent_config.get("type", "subprocess")
    sandbox_mode = bool(agent_config.get("sandbox", False))
    policy = TrustPolicy(trust=pack_trust, adapter_type=agent_type, sandbox=sandbox_mode)
    allowed, reason = policy.allowed()
    if explain_policy:
        click.echo(f"Policy evaluation for trust={pack_trust}, adapter={agent_type}, sandbox={sandbox_mode}:")
        click.echo(f"  {'ALLOWED' if allowed else 'DENIED'}: {reason or 'no restrictions'}")
        raise SystemExit(0 if allowed else 1)
    if not allowed:
        raise click.UsageError(reason or "adapter/trust combination not allowed")

    # Step 2: Generate run ID and begin audit trail
    run_id = generate_run_id()
    from evalforge.security.audit import AuditTrail
    from evalforge.security.sanitize import sanitize_config

    audit = AuditTrail(base_dir=output)
    audit.record("run_start", {
        "run_id": run_id,
        "pack": pack,
        "agent": sanitize_config(agent_config),
        "sandbox": bool(agent_config.get("sandbox", False)),
        "ci": ci,
    })

    if agent_config.get("sandbox", False):
        from evalforge.security.sandbox import SANDBOX_ALLOWLIST
        audit.record("sandbox_active", {"sandbox_allowlist": sorted(SANDBOX_ALLOWLIST)})

    # Step 3: Run all scenarios (or a filtered subset) and capture artifacts
    import time

    start_ms = int(time.time() * 1000)
    artifacts = runner.run_all(tags=tag_list, run_id=run_id, workers=workers)
    duration_ms = int(time.time() * 1000) - start_ms

    # Step 3: Score artifacts against scenario expectations
    from evalforge.cache import JudgeCache as _JudgeCache

    judge_cache = None if no_cache else _JudgeCache(base_dir=output)
    engine = ScoringEngine(runner.pack, judge_cache=judge_cache)
    judge_client = _resolve_judge(judge)
    run_score = engine.score_run(artifacts, judge=judge_client)

    # Step 4: Build the result payload for output and persistence
    pack_meta = runner.pack.pack
    result = {
        "run_id": run_id,
        "pack_name": pack_meta.name,
        "pack_version": pack_meta.version,
        "total_scenarios": (
            run_score.totals["passed"]
            + run_score.totals["warned"]
            + run_score.totals["failed"]
        ),
        "passed": run_score.totals["passed"],
        "warned": run_score.totals["warned"],
        "failed": run_score.totals["failed"],
        "exit_code": run_score.exit_code,
        "duration_ms": duration_ms,
        "safety_violations": run_score.safety_violations,
        "scenario_scores": {
            sid: {
                "status": ss.status,
                "safety_violations": ss.safety_violations,
                "metrics": {
                    m: {
                        "score": sr.score,
                        "threshold": sr.threshold,
                        "passed": sr.passed,
                        "category": sr.category,
                        "source": sr.source,
                        "error": sr.error,
                    }
                    for m, sr in ss.metric_results.items()
                },
            }
            for sid, ss in run_score.scenario_scores.items()
        },
    }

    result["cache_stats"] = engine.cache_stats if not no_cache else {}

    # Step 5 (optional): Compare against a saved baseline
    if baseline:
        from evalforge.baselines.store import BaselineStore
        from evalforge.comparison.engine import ComparisonEngine
        from evalforge.comparison.report import ComparisonReport

        store = BaselineStore(base_dir=f"{output}/baselines")
        try:
            baseline_obj = store.load(baseline)
            # Re-score the baseline's artifacts through the ScoringEngine
            # so we have a proper RunScore for comparison
            baseline_score = engine.score_run(baseline_obj.runs, judge=judge_client)
            comp_engine = ComparisonEngine(runner.pack)
            comp_result = comp_engine.compare(
                baseline_score=baseline_score,
                candidate_score=run_score,
                baseline=baseline_obj,
            )
            report = ComparisonReport(
                baseline_name=baseline,
                candidate_name=run_id,
                result=comp_result,
                candidate_score=run_score,
            )
            formatter = OutputFormatter(output_format)
            formatter.format_comparison(
                report, output_path=f"{output}/runs/{run_id}/comparison.md",
            )
            result["comparison"] = report.to_json() if output_format == "json" else {}
        except FileNotFoundError:
            click.echo(
                f"Warning: baseline '{baseline}' not found, skipping comparison",
                err=True,
            )

    # Step 6: Output
    formatter = OutputFormatter(output_format)
    output_content = formatter.format_run_result(result)
    if output_content:
        report_path = Path(f"{output}/runs/{run_id}/report.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(output_content)

    # Persist scores as JSON for later comparison and analysis
    with open(Path(f"{output}/runs/{run_id}/scores.json"), "w") as f:
        json.dump(result, f, indent=2)

    # Step 6a: Record audit trail completion
    audit.record("run_complete", {
        "run_id": run_id,
        "exit_code": run_score.exit_code,
        "passed": run_score.totals["passed"],
        "failed": run_score.totals["failed"],
        "safety_violations": run_score.safety_violations,
    })

    # Summary to stdout
    click.echo(f"Run complete: {run_id}")
    click.echo(
        f"  Passed: {run_score.totals['passed']},"
        f" Warned: {run_score.totals['warned']},"
        f" Failed: {run_score.totals['failed']}"
    )
    click.echo(f"  Exit code: {run_score.exit_code}")
    if run_score.safety_violations:
        click.echo(
            f"  Safety violations: {', '.join(run_score.safety_violations)}"
        )
