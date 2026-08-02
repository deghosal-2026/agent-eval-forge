"""Output formatting for CLI commands.

Provides a shared ``OutputFormatter`` class that renders results as JSON,
Markdown, terminal (Rich table), GitHub Actions, or HTML output across
all CLI commands. JSON is the default and is CI-friendly; Markdown is
designed for PR/commit comments; terminal uses Rich for colored display;
``github-actions`` generates output compatible with ``$GITHUB_STEP_SUMMARY``;
``html`` produces a self-contained dark-themed HTML report.

All ``rich`` imports are deferred to class- or method-scope to keep
``evalforge --help`` fast when terminal output is not requested.
"""

from __future__ import annotations

import json
from typing import Any

from evalforge.comparison.report import ComparisonReport


class OutputFormatter:
    """Format CLI output in JSON, Markdown, terminal, GitHub Actions, or HTML mode.

    Args:
        format: One of ``"json"``, ``"markdown"``, ``"terminal"``,
            ``"github-actions"``, or ``"html"``. Defaults to ``"json"``.
        quiet: If True, suppress printed JSON output (only relevant for JSON mode).
    """

    def __init__(self, format: str = "json", quiet: bool = False) -> None:
        self.format = format
        self.quiet = quiet

    def format_run_result(self, result: dict[str, Any]) -> str | None:
        """Format a run result payload.

        Args:
            result: The run result dictionary from ``run.py``.

        Returns:
            A formatted string for Markdown/terminal/GitHub Actions/HTML, or
            ``None`` for JSON output in quiet mode.
        """
        if self.format == "json":
            if not self.quiet:
                print(json.dumps(result, indent=2))
            return None
        elif self.format == "html":
            return _html_report(result)
        elif self.format == "github-actions":
            return self._run_result_github_actions(result)
        elif self.format == "markdown":
            return self._run_result_markdown(result)
        else:
            return self._run_result_terminal(result)

    def format_comparison(
        self, report: ComparisonReport, output_path: str | None = None
    ) -> str | None:
        """Format a comparison report.

        Args:
            report: The ``ComparisonReport`` to format.
            output_path: Optional file path to write the output to.

        Returns:
            A formatted string for Markdown/terminal/GitHub Actions, or
            ``None`` for JSON (printed directly).
        """
        if self.format == "json":
            output = json.dumps(report.to_json(), indent=2)
            if output_path:
                with open(output_path, "w") as f:
                    f.write(output)
            print(output)
            return None
        elif self.format == "markdown":
            md = report.to_markdown()
            if output_path:
                with open(output_path, "w") as f:
                    f.write(md)
            return md
        elif self.format == "github-actions":
            return self._comparison_github_actions(report)
        else:
            return self._comparison_terminal(report)

    def format_validation(self, results: dict[str, Any]) -> str | None:
        """Format validation results.

        Args:
            results: Validation target results dict.

        Returns:
            A formatted string for Markdown/terminal/GitHub Actions, or
            ``None`` for JSON.
        """
        if self.format == "json":
            print(json.dumps(results, indent=2))
            return None
        elif self.format == "github-actions":
            return self._validation_github_actions(results)
        elif self.format == "markdown":
            return self._validation_markdown(results)
        else:
            return self._validation_terminal(results)

    def format_test_result(self, summary: dict[str, Any]) -> str | None:
        """Format a multi-pack test run result.

        Args:
            summary: The aggregated test run summary dict.

        Returns:
            A formatted string or ``None`` for JSON.
        """
        if self.format == "json":
            print(json.dumps(summary, indent=2))
            return None
        elif self.format == "github-actions":
            return self._test_result_github_actions(summary)
        elif self.format == "markdown":
            return self._test_result_markdown(summary)
        else:
            return self._test_result_terminal(summary)

    def _run_result_markdown(self, result: dict[str, Any]) -> str:
        """Build a Markdown run report table."""
        lines = [
            f"# Run Result: {result['run_id']}",
            "",
            "## Summary",
            "| Metric | Value |",
            "|---|---|",
            f"| Pack | {result.get('pack_name', 'unknown')} |",
            f"| Scenarios | {result.get('total_scenarios', 0)} |",
            f"| Passed | {result.get('passed', 0)} |",
            f"| Warned | {result.get('warned', 0)} |",
            f"| Failed | {result.get('failed', 0)} |",
            f"| Duration | {result.get('duration_ms', 0)}ms |",
            f"| Exit Code | {result.get('exit_code', 0)} |",
        ]
        if result.get("safety_violations"):
            lines.append(
                f"| Safety Violations |"
                f" {', '.join(result['safety_violations'])} |"
            )
        lines.extend(["", "---"])
        return "\n".join(lines)

    def _run_result_github_actions(self, result: dict[str, Any]) -> str:
        """Build a GitHub Actions summary from a run result."""
        lines = [
            "## EvalForge Run Results",
            "",
            f"**Run:** `{result['run_id']}`  \n"
            f"**Pack:** {result.get('pack_name', 'unknown')} v{result.get('pack_version', '?')}  \n"
            f"**Duration:** {result.get('duration_ms', 0)}ms  \n"
            f"**Exit Code:** {result.get('exit_code', 0)}",
            "",
            "| Status | Count |",
            "|---|---|",
            f"| \u2705 Passed | {result.get('passed', 0)} |",
            f"| \u26a0\ufe0f Warned | {result.get('warned', 0)} |",
            f"| \u274c Failed | {result.get('failed', 0)} |",
        ]
        if result.get("safety_violations"):
            lines.append(
                f"| \U0001f6d1 Safety Violations |"
                f" {', '.join(result['safety_violations'])} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _run_result_terminal(self, result: dict[str, Any]) -> str:
        """Build a terminal (Rich) run report table."""
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title=f"Run: {result['run_id']}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Pack", result.get("pack_name", "unknown"))
        table.add_row("Scenarios", str(result.get("total_scenarios", 0)))
        table.add_row("Passed", str(result.get("passed", 0)))
        table.add_row("Warned", str(result.get("warned", 0)))
        table.add_row("Failed", str(result.get("failed", 0)))
        table.add_row("Duration", f"{result.get('duration_ms', 0)}ms")
        table.add_row("Exit Code", str(result.get("exit_code", 0)))
        if result.get("safety_violations"):
            table.add_row("Safety", ", ".join(result["safety_violations"]))
        console.print(table)
        return ""

    def _comparison_github_actions(self, report: ComparisonReport) -> str:
        """Build a GitHub Actions summary from a comparison report."""
        agg = report.result.aggregate
        lines = [
            "## EvalForge Comparison Report",
            "",
            f"**Baseline:** `{report.baseline_name}` \u2192"
            f" **Candidate:** `{report.candidate_name}`  \n",
            "| Metric | Value |",
            "|---|---|",
            f"| Total Scenarios | {agg['total_scenarios']} |",
            f"| Regressed | {agg['regressed']} |",
            f"| Improved | {agg['improved']} |",
            f"| New Failures | {agg['new_failures']} |",
            f"| New Passes | {agg['new_passes']} |",
            f"| Unchanged | {agg['unchanged']} |",
            f"| Score Delta | {agg['overall_score_delta']:+.3f} |",
        ]
        if report.candidate_score.safety_violations:
            lines.append(
                "| \U0001f6d1 Safety Violations |"
                f" {', '.join(report.candidate_score.safety_violations)} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _comparison_terminal(self, report: ComparisonReport) -> str:
        """Build a terminal (Rich) comparison report table."""
        from rich.console import Console
        from rich.table import Table

        console = Console()
        agg = report.result.aggregate
        console.print(
            f"[bold]Comparison: {report.baseline_name}"
            f" \u2192 {report.candidate_name}[/bold]"
        )
        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Total Scenarios", str(agg["total_scenarios"]))
        table.add_row("Regressed", f"[red]{agg['regressed']}[/red]")
        table.add_row("Improved", f"[green]{agg['improved']}[/green]")
        table.add_row("New Failures", f"[red]{agg['new_failures']}[/red]")
        table.add_row("New Passes", f"[green]{agg['new_passes']}[/green]")
        table.add_row("Unchanged", str(agg["unchanged"]))
        table.add_row("Score Delta", f"{agg['overall_score_delta']:+.3f}")
        if report.candidate_score.safety_violations:
            table.add_row(
                "Safety",
                f"[red]{', '.join(report.candidate_score.safety_violations)}[/red]",
            )
        console.print(table)
        return ""

    def _validation_github_actions(self, results: dict[str, Any]) -> str:
        """Build a GitHub Actions summary from validation results."""
        lines = ["## EvalForge Validation Results", ""]
        all_valid = all(r.get("valid") for r in results.values())
        if all_valid:
            lines.append("\u2705 All validations passed\n")
        for key, value in results.items():
            status = "\u2705" if value.get("valid") else "\u274c"
            lines.append(f"**{key}:** {status} \u2014 {value.get('message', '')}  ")
        lines.append("")
        return "\n".join(lines)

    def _validation_markdown(self, results: dict[str, Any]) -> str:
        """Build a Markdown validation report."""
        lines = ["# Validation Results", ""]
        for key, value in results.items():
            status = "\u2705" if value.get("valid") else "\u274c"
            lines.append(f"## {key} {status}")
            for k, v in value.items():
                if k != "valid":
                    lines.append(f"- **{k}:** {v}")
            lines.append("")
        lines.append("---")
        return "\n".join(lines)

    def _validation_terminal(self, results: dict[str, Any]) -> str:
        """Build a terminal (Rich) validation report."""
        from rich.console import Console

        console = Console()
        all_valid = all(r.get("valid") for r in results.values())
        if all_valid:
            console.print("[green]\u2713 All validations passed[/green]")
        for key, value in results.items():
            status = (
                "[green]\u2713[/green]"
                if value.get("valid")
                else "[red]\u2717[/red]"
            )
            console.print(f"{status} {key}: {value.get('message', '')}")
        return ""

    def _test_result_github_actions(self, summary: dict[str, Any]) -> str:
        """Build a GitHub Actions summary from a multi-pack test run."""
        lines = [
            "## EvalForge Test Run Results",
            "",
            f"**Packs:** {summary.get('packs', 0)}  \n"
            f"**Scenarios:** {summary.get('total_scenarios', 0)}  \n"
            f"**Duration:** {summary.get('duration_ms', 0)}ms",
            "",
            "| Status | Count |",
            "|---|---|",
            f"| \u2705 Passed | {summary.get('passed', 0)} |",
            f"| \u26a0\ufe0f Warned | {summary.get('warned', 0)} |",
            f"| \u274c Failed | {summary.get('failed', 0)} |",
        ]
        if summary.get("safety_violations"):
            lines.append(
                "| \U0001f6d1 Safety Violations |"
                f" {', '.join(summary['safety_violations'])} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _test_result_markdown(self, summary: dict[str, Any]) -> str:
        """Build a Markdown multi-pack test run report."""
        lines = [
            "# EvalForge Test Run Results",
            "",
            "## Aggregate Summary",
            "| Metric | Value |",
            "|---|---|",
            f"| Packs | {summary.get('packs', 0)} |",
            f"| Total Scenarios | {summary.get('total_scenarios', 0)} |",
            f"| Passed | {summary.get('passed', 0)} |",
            f"| Warned | {summary.get('warned', 0)} |",
            f"| Failed | {summary.get('failed', 0)} |",
            f"| Duration | {summary.get('duration_ms', 0)}ms |",
        ]
        if summary.get("safety_violations"):
            lines.append(
                "| Safety Violations |"
                f" {', '.join(summary['safety_violations'])} |"
            )
        lines.extend(["", "## Per-Pack Results", ""])
        for r in summary.get("results", []):
            pack = r.get("pack_name", r.get("pack_path", "unknown"))
            if "error" in r:
                lines.append(f"- **{pack}**: \u274c {r['error']}")
            else:
                lines.append(
                    f"- **{pack}**: \u2705 {r.get('passed', 0)} passed,"
                    f" \u26a0\ufe0f {r.get('warned', 0)} warned,"
                    f" \u274c {r.get('failed', 0)} failed"
                )
        lines.append("")
        return "\n".join(lines)

    def _test_result_terminal(self, summary: dict[str, Any]) -> str:
        """Build a terminal (Rich) multi-pack test run report."""
        from rich.console import Console
        from rich.table import Table

        console = Console()
        console.print("[bold]EvalForge Test Run Results[/bold]")
        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Packs", str(summary.get("packs", 0)))
        table.add_row("Scenarios", str(summary.get("total_scenarios", 0)))
        table.add_row("Passed", str(summary.get("passed", 0)))
        table.add_row("Warned", str(summary.get("warned", 0)))
        table.add_row("Failed", str(summary.get("failed", 0)))
        table.add_row("Duration", f"{summary.get('duration_ms', 0)}ms")
        if summary.get("safety_violations"):
            table.add_row(
                "Safety", ", ".join(summary["safety_violations"])
            )
        console.print(table)

        for r in summary.get("results", []):
            pack = r.get("pack_name", r.get("pack_path", "unknown"))
            if "error" in r:
                console.print(f"  [red]\u2717[/red] {pack}: {r['error']}")
            else:
                console.print(
                    f"  [green]\u2713[/green] {pack}:"
                    f" {r.get('passed', 0)}p/{r.get('warned', 0)}w/{r.get('failed', 0)}f"
                )

        return ""


def _html_report(result: dict[str, Any]) -> str:
    """Render a run result as a self-contained dark-themed HTML report.

    Args:
        result: The run result dictionary from ``run.py`` containing
            summary, scenario_scores, and optional cache_stats.

    Returns:
        A complete HTML document string with embedded CSS styling.
    """
    summary = result.get("summary", result)
    passed = summary.get("passed", 0)
    warned = summary.get("warned", 0)
    failed = summary.get("failed", 0)
    total = summary.get("total_scenarios", passed + warned + failed)
    pct = f"{(passed / total * 100):.0f}%" if total else "N/A"
    # Color the pass-rate card based on failure presence: green=all pass,
    # red=more failures than passes, amber=mixed
    color = "#22c55e" if failed == 0 else "#ef4444" if failed > passed else "#f59e0b"

    safety = summary.get("safety_violations", [])
    safety_html = ""
    if safety:
        violations = ", ".join(safety)
        safety_html = (
            '<div class="sa-card" style="--c:#ef4444">'
            "<h3>\U0001f6e1 Safety Violations</h3>"
            f"<p>{violations}</p></div>"
        )

    scenarios_html = ""
    for s in result.get("scenario_scores", {}).items():
        sid, sd = s
        st = sd.get("status", "?")
        sc = "#22c55e" if st == "passed" else "#ef4444" if st == "failed" else "#f59e0b"
        metrics = sd.get("metrics", {})
        score_vals = []
        for _mn, mr in metrics.items():
            sval = mr.get("score")
            if sval is not None:
                try:
                    score_vals.append(f"{float(sval):.2f}")
                except (TypeError, ValueError):
                    score_vals.append(str(sval))
        score_str = " / ".join(score_vals) if score_vals else "\u2014"
        scenarios_html += (
            f'<tr style="background:{sc}10">'
            f"<td>{sid}</td>"
            f'<td style="color:{sc};font-weight:600">{st}</td>'
            f"<td>{score_str}</td>"
            f"</tr>\n"
        )

    cache_html = ""
    cache_stats = result.get("cache_stats", {})
    if cache_stats:
        cache_html = (
            '<div class="sa-card" style="--c:#8b5cf6">'
            "<h3>\U0001f4be Judge Cache</h3><table>"
            "<tr><th>Hits</th><th>Misses</th><th>Size</th></tr>"
            f"<tr><td>{cache_stats.get('hits', 0)}</td>"
            f"<td>{cache_stats.get('misses', 0)}</td>"
            f"<td>{cache_stats.get('size', 0)}</td></tr>"
            "</table></div>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EvalForge Report — {summary.get('run_id', '...')}</title>
<style>
:root{{--bg:#0f172a;--surface:#1e293b;--border:#334155;--text:#e2e8f0;--muted:#94a3b8}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;min-height:100vh}}
.container{{max-width:960px;margin:0 auto;padding:2rem 1.5rem}}
h1{{font-size:1.75rem;margin-bottom:.25rem;color:#f1f5f9}}
h2{{font-size:1.25rem;margin-bottom:1rem;color:#cbd5e1}}
h3{{font-size:1rem;margin-bottom:.5rem;color:#cbd5e1}}
.pack-tag{{color:var(--muted);font-size:.85rem;margin-bottom:2rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin-bottom:1.5rem}}
.card{{
    background:var(--surface);
    border:1px solid var(--border);
    border-radius:10px;
    padding:1.25rem;
    text-align:center
}}
.card .val{{
    font-size:2rem;
    font-weight:700;
    color:var(--c,{color})
}}
.card .lbl{{
    font-size:.8rem;
    color:var(--muted);
    text-transform:uppercase;
    letter-spacing:.05em;
    margin-top:.25rem
}}
.sa-card{{
    background:var(--surface);
    border:1px solid var(--border);
    border-left:4px solid var(--c,#8b5cf6);
    border-radius:10px;
    padding:1.25rem;
    margin-bottom:1rem
}}
.sa-card h3{{margin-bottom:.5rem;color:var(--c,#8b5cf6)}}
.sa-card p{{color:var(--muted);font-size:.9rem}}
table{{
    width:100%;
    border-collapse:collapse;
    background:var(--surface);
    border:1px solid var(--border);
    border-radius:10px;
    overflow:hidden
}}
th,td{{
    padding:.625rem .875rem;
    text-align:left;
    border-bottom:1px solid var(--border);
    font-size:.9rem
}}
th{{
    background:#1a2332;
    color:var(--muted);
    font-weight:600;
    text-transform:uppercase;
    letter-spacing:.04em;
    font-size:.75rem
}}
tr:last-child td{{border-bottom:none}}
.footer{{
    text-align:center;
    color:var(--muted);
    font-size:.8rem;
    margin-top:2rem;
    padding-top:1.5rem;
    border-top:1px solid var(--border)
}}
.footer-exit{{margin-top:.5rem;font-size:.8rem}}
</style>
</head>
<body>
<div class="container">
<h1>EvalForge Run Report</h1>
<p class="pack-tag">
    Pack: {summary.get('pack_name', '?')} v{summary.get('pack_version', '?')}
    &middot; Run: {summary.get('run_id', '?')}
</p>

<div class="grid">
<div class="card" style="--c:#22c55e">
    <div class="val">{passed}</div>
    <div class="lbl">Passed</div>
</div>
<div class="card" style="--c:#f59e0b">
    <div class="val">{warned}</div>
    <div class="lbl">Warned</div>
</div>
<div class="card" style="--c:#ef4444">
    <div class="val">{failed}</div>
    <div class="lbl">Failed</div>
</div>
<div class="card" style="--c:{color}">
    <div class="val">{pct}</div>
    <div class="lbl">Pass Rate</div>
</div>
</div>

{safety_html}
{cache_html}

<h2>Scenario Results</h2>
<table>
<thead><tr><th>Scenario</th><th>Status</th><th>Scores</th></tr></thead>
<tbody>{scenarios_html}</tbody>
</table>

<div class="footer">
<p>Generated by EvalForge v0.1.0 &middot; Duration: {summary.get('duration_ms', 0)}ms</p>
<p class="footer-exit">Exit code: {summary.get('exit_code', 0)}</p>
</div>
</div>
</body>
</html>"""
