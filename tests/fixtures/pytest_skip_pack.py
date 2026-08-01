"""Test file used by test_pytest_plugin to verify scenario_pack fixture skips."""
pytest_plugins = ["evalforge.pytest_plugin"]


def test_skip(scenario_pack):
    pass
