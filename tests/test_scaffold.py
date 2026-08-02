"""Placeholder test ensuring the scaffold is importable and testable.

M0's purpose is proving the plumbing: importable package, working test
runner, enforced version. Real behavioral tests land from M1 onward
(model round-trips, adapters, scorers), at which point this file can be
retired or folded into a package-level sanity suite.

The version assertion is intentionally strict: the package `__version__`
and the static `[project] version` in pyproject.toml must be kept in sync
(see src/evalforge/__init__.py), and this test catches a drift at the only
place both are reachable from Python.
"""

from evalforge import __version__


def test_version() -> None:
    assert __version__ == "0.1.0"
