"""Test file used by test_pytest_plugin to verify agent_config fixture skips."""
pytest_plugins = ["evalforge.pytest_plugin"]


def test_skip(agent_config):
    pass
