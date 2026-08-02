"""Comparison engine: candidate-vs-baseline deltas and reports (spec §"Comparison Model").

Provides ComparisonEngine (3-level delta computation) and ComparisonReport
(JSON + Markdown output). See individual module docs for details.

The comparison pipeline:
1. :class:`ComparisonEngine` takes a baseline RunScore and a candidate RunScore
   and computes per-scenario, per-family, and aggregate deltas.
2. :class:`ComparisonReport` formats the result as JSON or Markdown for CI
   and human consumption.
"""

from evalforge.comparison.engine import ComparisonEngine, ComparisonResult
from evalforge.comparison.report import ComparisonReport

__all__ = ["ComparisonEngine", "ComparisonReport", "ComparisonResult"]
