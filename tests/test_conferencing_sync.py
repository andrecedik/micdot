import threading
import pytest
from collections.abc import Callable
from micdot.audio.backend import StubAudioBackend
from micdot.conferencing.base import ConferencingPlugin
from micdot.conferencing.sync import ConferencingSync


class StubPlugin(ConferencingPlugin):
    bundle_id = "com.stub"
    name = "Stub"

    def __init__(self, running: bool = True, in_meeting: bool = True, mute: bool = False):
        self._running = running
        self._in_meeting = in_meeting
        self._mute = mute
        self.set_mute_calls: list[bool] = []
        self._on_change: Callable[[bool], None] | None = None

    def is_running(self) -> bool: return self._running
    def is_in_meeting(self) -> bool: return self._in_meeting
    def get_mute(self) -> bool | None: return self._mute if self._in_meeting else None

    def set_mute(self, muted: bool) -> None:
        self._mute = muted
        self.set_mute_calls.append(muted)

    def start_observing(self, on_change: Callable[[bool], None]) -> None:
        self._on_change = on_change

    def stop_observing(self) -> None:
        self._on_change = None

    def fire(self, muted: bool) -> None:
        if self._on_change:
            self._on_change(muted)


def test_on_mute_change_propagates_to_plugin_in_meeting():
    backend = StubAudioBackend()
    plugin = StubPlugin(running=True, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    sync.on_mute_change(True)

    assert plugin.set_mute_calls == [True]
    sync.stop()


def test_on_mute_change_skips_plugin_not_in_meeting():
    backend = StubAudioBackend()
    plugin = StubPlugin(running=True, in_meeting=False)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    sync.on_mute_change(True)

    assert plugin.set_mute_calls == []
    sync.stop()


def test_on_mute_change_skips_plugin_not_running():
    backend = StubAudioBackend()
    plugin = StubPlugin(running=False, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    sync.on_mute_change(True)

    assert plugin.set_mute_calls == []
    sync.stop()


def test_app_change_updates_backend():
    backend = StubAudioBackend(initial_mute=False)
    plugin = StubPlugin(running=True, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    plugin.fire(True)

    assert backend.get_mute() is True
    sync.stop()


def test_echo_suppression_ignores_our_own_set():
    backend = StubAudioBackend(initial_mute=False)
    plugin = StubPlugin(running=True, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    # MicDot mutes → propagated to plugin
    sync.on_mute_change(True)
    # AX notifies us back with the same state we just set (our echo)
    plugin.fire(True)

    # Backend must NOT have been changed (it was our echo)
    assert backend.get_mute() is False
    sync.stop()


def test_genuine_app_change_after_our_set_updates_backend():
    backend = StubAudioBackend(initial_mute=False)
    plugin = StubPlugin(running=True, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    sync.on_mute_change(True)   # MicDot mutes
    plugin.fire(True)            # echo — suppressed
    plugin.fire(False)           # user immediately unmutes inside app

    assert backend.get_mute() is False
    sync.stop()


def test_stop_unregisters_observers():
    backend = StubAudioBackend()
    plugin = StubPlugin(running=True, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()
    sync.stop()

    assert plugin._on_change is None


def test_start_skips_incompatible_plugins():
    backend = StubAudioBackend()

    class _Incompatible(StubPlugin):
        def _get_installed_version(self): return "1.0.0"
        def is_compatible(self): return False

    bad = _Incompatible()
    sync = ConferencingSync([bad], backend)
    sync.start()

    # incompatible plugin should never be observed
    assert bad._on_change is None
    sync.stop()
