"""Failure taxonomy and analytics (spec §"Analytics Module").

Provides failure classification, aggregated run analytics, and
run-vs-run taxonomy comparison.  See :mod:`evalforge.analytics.taxonomy`
for the public API.
"""

from evalforge.analytics.taxonomy import (
    AnalyticsReport,
    FailureCategory,
    FailureClassification,
    FailureTaxonomy,
    classify_failure,
)

__all__ = [
    "AnalyticsReport",
    "FailureCategory",
    "FailureClassification",
    "FailureTaxonomy",
    "classify_failure",
]
