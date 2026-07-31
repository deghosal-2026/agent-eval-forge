"""Tests for the CLI entry point.

Uses click's in-process `CliRunner` rather than spawning subprocesses so
these tests are fast and deterministic, and so a failure surfaces the
traceback directly in pytest. (Integration-level CLI tests that exercise the
installed console script and real exit codes are deferred to M7, where the
full `run`/`compare`/`baseline` surface exists.)
"""

from click.testing import CliRunner

from evalforge.cli.__main__ import main


def test_version_command() -> None:
    """`evalforge version` prints the package version and exits 0.

    Guards against two failure classes: a broken console-script wiring
    (import error when resolving the entry point) and a version drift
    between the package and the CLI output.
    """
    runner = CliRunner()
    result = runner.invoke(main, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == "0.1.0"
