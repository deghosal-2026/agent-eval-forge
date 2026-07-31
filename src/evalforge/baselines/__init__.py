"""Golden baselines: save, load, validate, and list accepted agent runs.

A baseline is the explicit "we approved this" snapshot for a scenario pack —
the thing every future change is compared against (spec §"Baseline Model").
Explicit baselines beat "whatever happened to run last": a candidate run only
passes if it matches an accepted reference, not the last CI run.
"""

from evalforge.baselines.model import Baseline
from evalforge.baselines.store import BaselineStore

__all__ = ["Baseline", "BaselineStore"]
