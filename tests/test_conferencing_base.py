import sys
import pytest
from micdot.conferencing.base import ConferencingPlugin, _version_tuple


# ---- version comparison helpers ----

def test_version_tuple_parses_semver():
    assert _version_tuple("5.12.3") == (5, 12, 3)


def test_version_tuple_parses_two_part():
    assert _version_tuple("1.0") == (1, 0)


def test_version_tuple_returns_empty_on_garbage():
    assert _version_tuple("not-a-version") == ()


# ---- ConferencingPlugin.is_compatible ----

class _StubPlugin(ConferencingPlugin):
    bundle_id = "com.test.stub"
    name = "Stub"

    def __init__(self, installed_version=None):
        self._installed_version = installed_version

    def _get_installed_version(self):
        return self._installed_version

    def is_running(self): return True
    def is_in_meeting(self): return True
    def get_mute(self): return False
    def set_mute(self, muted): pass
    def start_observing(self, on_change): pass
    def stop_observing(self): pass


def test_is_compatible_true_with_no_version_constraints():
    assert _StubPlugin(installed_version="1.0.0").is_compatible() is True


def test_is_compatible_false_when_platform_unsupported(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    p = _StubPlugin(installed_version="5.0.0")
    assert p.is_compatible() is False


def test_is_compatible_false_when_installed_below_min():
    p = _StubPlugin(installed_version="4.9.9")
    p.min_version = "5.0.0"
    assert p.is_compatible() is False


def test_is_compatible_true_when_installed_meets_min():
    p = _StubPlugin(installed_version="5.0.0")
    p.min_version = "5.0.0"
    assert p.is_compatible() is True


def test_is_compatible_true_when_installed_version_unknown():
    p = _StubPlugin(installed_version=None)
    p.min_version = "5.0.0"
    # Can't check version, so allow it
    assert p.is_compatible() is True
