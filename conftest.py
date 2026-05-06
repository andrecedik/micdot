import pytest


def pytest_sessionfinish(session, exitstatus):
    """Return exit code 0 when no tests are collected."""
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
