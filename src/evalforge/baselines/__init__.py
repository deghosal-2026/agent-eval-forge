"""Golden baselines: save, load, validate, and list accepted agent runs.

A baseline is the explicit "we approved this" snapshot for a scenario pack —
the thing every future change is compared against (spec §"Baseline Model").
Explicit baselines beat "whatever happened to run last": a candidate run only
passes if it matches an accepted reference, not the last CI run.

Usage:
    store = BaselineStore()
    store.save(Baseline(name="v1.0", pack="core", pack_version="1.0.0", runs=artifacts))
    loaded = store.load("v1.0")
    warning = store.validate("v1.0", pack_version="1.0.0")  # warns on mismatch
"""

from evalforge.baselines.model import Baseline
from evalforge.baselines.store import BaselineStore

__all__ = ["Baseline", "BaselineStore"]
