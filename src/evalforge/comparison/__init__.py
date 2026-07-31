"""Comparison engine: candidate-vs-baseline deltas and reports (spec §"Comparison Model").

Provides ComparisonEngine (3-level delta computation) and ComparisonReport
(JSON + Markdown output). See individual module docs for details.
"""

from evalforge.comparison.engine import ComparisonEngine, ComparisonResult
from evalforge.comparison.report import ComparisonReport

__all__ = ["ComparisonEngine", "ComparisonReport", "ComparisonResult"]
