"""Comparison report — JSON and Markdown report generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evalforge.comparison.engine import ComparisonResult
from evalforge.scoring.result import RunScore


@dataclass
class ComparisonReport:
    baseline_name: str
    candidate_name: str
    result: ComparisonResult
    candidate_score: RunScore

    def to_json(self) -> dict[str, Any]:
        return {
            "baseline_name": self.baseline_name,
            "candidate_name": self.candidate_name,
            "aggregate": {
                "total_scenarios": self.result.aggregate["total_scenarios"],
                "regressed": self.result.aggregate["regressed"],
                "improved": self.result.aggregate["improved"],
                "new_failures": self.result.aggregate["new_failures"],
                "new_passes": self.result.aggregate["new_passes"],
                "unchanged": self.result.aggregate["unchanged"],
                "overall_score_delta": self.result.aggregate["overall_score_delta"],
                "candidate_totals": self.candidate_score.totals,
                "candidate_exit_code": self.candidate_score.exit_code,
                "safety_violations": self.candidate_score.safety_violations,
                "cost_delta_usd": self.result.aggregate.get("cost_delta_usd", 0),
            },
            "scenario_deltas": self.result.scenario_deltas,
            "family_deltas": self.result.family_deltas,
        }

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Comparison Report: {self.baseline_name} \u2192 {self.candidate_name}")
        lines.append("")

        agg = self.result.aggregate
        lines.append("## Summary")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(f"| Total Scenarios | {agg['total_scenarios']} |")
        lines.append(f"| Regressed | {agg['regressed']} |")
        lines.append(f"| Improved | {agg['improved']} |")
        lines.append(f"| New Failures | {agg['new_failures']} |")
        lines.append(f"| New Passes | {agg['new_passes']} |")
        lines.append(f"| Unchanged | {agg['unchanged']} |")
        lines.append(f"| Overall Score Delta | {agg['overall_score_delta']:+.3f} |")
        lines.append(f"| Cost Delta (USD) | {agg.get('cost_delta_usd', 0):+.6f} |")
        lines.append(f"| Exit Code | {self.candidate_score.exit_code} |")
        if self.candidate_score.safety_violations:
            lines.append(
                f"| Safety Violations | {', '.join(self.candidate_score.safety_violations)} |"
            )
        lines.append("")

        lines.append("## Per-Scenario Deltas")
        lines.append("| Scenario | Baseline | Candidate | Delta | Status |")
        lines.append("|---|---|---|---|---|")
        for sid, delta in sorted(self.result.scenario_deltas.items()):
            label: str
            if delta["regressed"]:
                label = "regressed"
            elif delta["improved"]:
                label = "improved"
            else:
                label = "unchanged"
            delta_str = (
                f"{delta['delta']:+.3f}" if delta["delta"] is not None else "-"
            )
            lines.append(
                f"| {sid} | {delta['baseline_score'] or '-'} | "
                f"{delta['candidate_score'] or '-'} | {delta_str} | {label} |"
            )
        lines.append("")

        if self.result.family_deltas:
            lines.append("## Per-Family Deltas")
            lines.append("| Family | Baseline Avg | Candidate Avg | Delta |")
            lines.append("|---|---|---|---|")
            for fam, fd in sorted(self.result.family_deltas.items()):
                lines.append(
                    f"| {fam} | {fd['baseline_avg']:.3f} | {fd['candidate_avg']:.3f} | "
                    f"{fd['score_delta']:+.3f} |"
                )
            lines.append("")

        lines.append("---")
        return "\n".join(lines)
