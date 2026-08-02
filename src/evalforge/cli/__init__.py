"""Command-line interface for EvalForge.

Public package entry point. The actual command implementations live in
`evalforge.cli.__main__` to keep the package namespace clean: `__init__.py`
only re-exports the Click group `main` that the console script
(`evalforge = "evalforge.cli:main"` in pyproject.toml) resolves to.

Keeping the implementation in `__main__.py` (rather than inline here) means
`python -m evalforge.cli` also works and avoids import-order pitfalls between
the console-script wrapper and package-internal imports.
"""

from evalforge.cli.__main__ import main

__all__ = ["main"]
